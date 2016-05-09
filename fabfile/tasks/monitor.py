from fabfile.utils.zabbix import get_zbx
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.tasks.install import pkg_install
import re

HOSTGROUPS = {
    'cfgm': {
        "hostgroup": "Contrail Controllers",
        "templates": [
            "Template Contrail Controller Apps",
            "Template App HTTP Service",
            "Template App Memcached Service",
            "Template App MySQL",
            "Template App NTP Service",
            "Template OS Linux",
            "Template RabbitMQ",
            "Template Redis 2",
            "Template ZooKeeper Info"
        ],
        "repos": ["contrail", "memcached", "mysql", "rabbitmq", "redis", "zookeeper"]
    },
    'compute': {
        "hostgroup": "Compute Nodes",
        "templates": [
            "Template OS Linux",
            "Template App Contrail vrouter agent",
            "Template App NTP Service",
            "Template OS Linux (Template App Zabbix Agent)",

        ],
        "repos": ["contrail"]
    }
}

ZBX_TEMPLATE_CLONE_PATH = "/tmp/zabbix-templates"
ZBX_TEMPLATE_REPO = "https://github.com/hkumarmk/zabbix-templates.git"


def zabbix_repo_install():
    zabbix_release_url = \
        "http://repo.zabbix.com/zabbix/3.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_3.0-1+trusty_all.deb"
    with settings(warn_only=True):
        sudo(
            "wget " + zabbix_release_url + " -O zabbix-release.deb; "
            "dpkg -i zabbix-release.deb; apt-get update; "
        )


@roles('monitor')
@task
def setup_zabbix_server():
    zabbix_repo_install()
    with settings(warn_only=True):
        sudo(
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get install -q -y --force-yes zabbix-server-mysql zabbix-frontend-php crudini python-pip git; "
            "pip install xmltodict; "
            "mysql -e \"create database zabbix; "
            "create user 'zabbix'@'localhost'; "
            "GRANT ALL ON zabbix.* TO 'zabbix'@'localhost';\"; "
            "gunzip /usr/share/doc/zabbix-server-mysql/create.sql.gz; "
            "mysql -uzabbix zabbix < /usr/share/doc/zabbix-server-mysql/create.sql; "
            "crudini --set /etc/php5/apache2/php.ini Date date.timezone $(date +%Z); "
            "service zabbix-server restart;"
            "service apache2 reload; "
        )
    configure_zabbix_frontend()


def monitor_server(url=False):
    server = env.roledefs.get('monitor', ['127.0.0.1'])[0].split('@')[1]
    if url:
        return "http://%s/zabbix" % server
    else:
        return server


@roles('monitor')
@task
def configure_zabbix_frontend():
    with settings(warn_only=True):
        sudo(
            "mkdir -p /etc/zabbix/web/\n"
            "cat << 'EOF' > /etc/zabbix/web/zabbix.conf.php\n"
            "<?php\n"
            "global $DB;\n"
            "$DB['TYPE']     = 'MYSQL';\n"
            "$DB['SERVER']   = 'localhost';\n"
            "$DB['PORT']     = '0';\n"
            "$DB['DATABASE'] = 'zabbix';\n"
            "$DB['USER']     = 'zabbix';\n"
            "$DB['PASSWORD'] = '';\n"
            "$DB['SCHEMA'] = '';\n"
            "$ZBX_SERVER      = 'localhost';\n"
            "$ZBX_SERVER_PORT = '10051';\n"
            "$ZBX_SERVER_NAME = '';\n"
            "$IMAGE_FORMAT_DEFAULT = IMAGE_FORMAT_PNG;\n"
            "?>\n"
            "EOF\n"
        )


@task
def setup_zabbix_agent():
    zabbix_repo_install()
    pkg_install(['zabbix-agent'])
    with settings(warn_only=True):
        sudo("cat << EOF > /etc/zabbix/zabbix_agentd.conf\n"
             "PidFile=/var/run/zabbix/zabbix_agentd.pid\n"
             "LogFile=/var/log/zabbix/zabbix_agentd.log\n"
             "LogFileSize=0\n"
             "Server=" + monitor_server() + "\n"
             "ServerActive=" + monitor_server() + "\n"
             "Hostname=$(hostname)\n"
             "Include=/etc/zabbix/zabbix_agentd.d/\n"
             "EOF\n"
             "service zabbix-agent restart"
             )


def setup_hostgroups(zbx):
    for hg in HOSTGROUPS.values():
        zbx.hostgroup.add(hg["hostgroup"])


@task
def copy(local_path, remote_path, mode=0644, follow_through=None,):
    """ Copy files/directories remotely
    :param local_path: source path
    :param remote_path: destination path
    :param mode: file mode
    :param follow_through: Any script to run after copy
    """
    #with quiet():
    sudo("mkdir -p %s" % remote_path)
    put(local_path, remote_path, True, mode=mode)
    if follow_through:
        sudo(follow_through)


def install_templates(zbx):
    local(
        "rm -fr %s" % ZBX_TEMPLATE_CLONE_PATH + "; "
        "git clone  %s %s" % (ZBX_TEMPLATE_REPO, ZBX_TEMPLATE_CLONE_PATH) + "; "
    )

    for role, hg_data in HOSTGROUPS.iteritems():
        for repo in hg_data.get("repos", []):
            repo_path = os.path.join(ZBX_TEMPLATE_CLONE_PATH, repo)
            entries = os.listdir(repo_path)
            for entry in entries:
                file_path=os.path.join(repo_path, entry)
                if re.match(r"zbx_.*_export_.*.xml", entry):
                    import_templates(zbx, file_path)
                if re.match(r"userparameter_.*.conf", entry):
                    execute(copy, file_path, "/etc/zabbix/zabbix_agentd.d/",
                            follow_through="service zabbix-agent restart",
                            hosts=env.roledefs[role]
                            )
                if entry == "scripts":
                    execute(copy, file_path + "/*", "/etc/zabbix/scripts/",
                            0755, hosts=env.roledefs[role])
                if entry == "externalscripts":
                    execute(copy, file_path + "/*",
                            "/usr/lib/zabbix/externalscripts/",
                            0755, hosts=env.roledefs['monitor'])


def setup_hosts(zbx):
    host_dict = {}
    for role, hg in HOSTGROUPS.iteritems():
        templates = hg["templates"]
        group = hg["hostgroup"]
        host_list = set(env.roledefs.get(role, []))
        for host in host_list:
            with quiet(), settings(host_string=host):
                hostname = run('hostname')
            ip = host.split('@')[1]
            if host_dict.get(hostname, None):
                host_dict[hostname]['hostgroups'].append(group)
                templates_combined = host_dict[hostname]['templates'].union(templates)
                host_dict[hostname]['templates'] = templates_combined
            else:
                host_dict.update({hostname: {
                    'hostgroups': [group], 'ip': ip, 'templates': set(templates)
                }})
    for hostname, params in host_dict.iteritems():
        print "Adding host %s(%s)" % (hostname, params['ip'])
        if zbx.host.get(hostname):
            zbx.host.update(hostname, **params)
        else:
            zbx.host.add(hostname, **params)


def import_templates(zbx, template_file=None):
    if template_file:
        print "Importing the templates"
        with open(template_file, 'r') as f:
            zbx.template.import_(f.read())


def setup_monitors():
    env_monitor = env.get('monitor', {})
    zbx = get_zbx(monitor_server(True), **env_monitor)
    setup_hostgroups(zbx)
    install_templates(zbx)
    setup_hosts(zbx)


@roles('monitor')
@task
def setup_zabbix():
    setup_zabbix_server()
    all_monitored_hosts = []
    for role in HOSTGROUPS.keys():
        all_monitored_hosts.extend(env.roledefs.get(role, []))
    execute(setup_zabbix_agent, hosts=all_monitored_hosts)
    setup_monitors()

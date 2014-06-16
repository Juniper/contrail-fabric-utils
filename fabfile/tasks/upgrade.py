import os
import copy

from fabfile.utils.fabos import *
from fabfile.config import *
from fabfile.tasks.services import *
from fabfile.tasks.misc import rmmod_vrouter, create_default_secgrp_rules
from fabfile.tasks.rabbitmq import setup_rabbitmq_cluster
from fabfile.tasks.helpers import compute_reboot, reboot_node
from fabfile.tasks.provision import setup_vrouter, setup_vrouter_node,\
     setup_contrail_horizon_node, setup_contrail_horizon
from fabfile.tasks.install import install_pkg_all, create_install_repo,\
     create_install_repo_node, upgrade_pkgs, install_pkg_node, yum_install,  apt_install

RELEASES_WITH_QPIDD = ('1.0', '1.01', '1.02', '1.03')
RELEASES_WITH_ZOO_3_4_3 = ('1.0', '1.01', '1.02', '1.03', '1.04')
VENVS = ['vrouter-venv', 'control-venv', 'database-venv', 'api-venv', 'analytics-venv']


@task
def backup_source_list():
    run('mv /etc/apt/sources.list /etc/apt/sources.list.upgradesave')

@task
def create_contrail_source_list():
    run('echo "deb file:/opt/contrail/contrail_install_repo ./" > /etc/apt/sources.list')
@task
def restore_source_list():
    with settings(warn_only=True):
        run('mv /etc/apt/sources.list.upgradesave /etc/apt/sources.list')

def fix_vizd_param():
    if run('ls /etc/contrail/vizd_param').succeeded:
        run('grep -q ANALYTICS_SYSLOG_PORT /etc/contrail/vizd_param || echo "ANALYTICS_SYSLOG_PORT=-1" >> /etc/contrail/vizd_param')

def fix_redis_uve_conf():
    redis_uve_conf = '/etc/contrail/redis-uve.conf'
    with settings(warn_only=True):
        redis_uve_conf_exists = run('ls %s' % redis_uve_conf).succeeded

        if redis_uve_conf_exists:
            run('service redis-uve stop')
            run('rm -f /var/lib/redis/dump-uve.rdb')
            run("sed 's/^slaveof/#&/' %s > %s.new" % (redis_uve_conf, redis_uve_conf))
            run("mv %s.new %s" % (redis_uve_conf, redis_uve_conf))

        run('rm -f /etc/contrail/sentinel.conf')
        run('rm -f /etc/contrail/supervisord_analytics_files/redis-sentinel.ini')

    if (detect_ostype() in ['centos'] and get_release() in ['1.05', '1.06']):
        with settings(warn_only=True):
            run('mv -f /etc/contrail/supervisord_analytics.conf.rpmnew /etc/contrail/supervisord_analytics.conf')

@task
@EXECUTE_TASK
@roles('compute')
def fixup_agent_param():
    if (detect_ostype() in ['Ubuntu'] and get_release() == '1.04'):
        # fix dev=vhost0 to the host interface
        dev = run("grep eth-port /etc/contrail/agent.conf | grep name|cut -f2 -d '>'|cut -f1 -d'<'")
        run("sed 's/dev=.*/dev=%s/g' /etc/contrail/agent_param > agent_param.newer" % (dev))
        run("mv agent_param.newer /etc/contrail/agent_param")

@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_zookeeper():
    execute('upgrade_zookeeper_node', env.host_string)

@task
def upgrade_zookeeper_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                print "No need to upgrade specifically zookeeper in ubuntu."
                return
            with settings(warn_only=True):
                run('rpm -e --nodeps zookeeper zookeeper-lib zkpython')
            yum_install(['zookeeper'])
            run('yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail_install_repo reinstall contrail-config')
            run('chkconfig zookeeper on')

@task
@serial
@roles('cfgm')
def start_zookeeper():
    execute("create_install_repo_node", env.host_string)
    run("supervisorctl -s http://localhost:9004 stop contrail-api:0")
    run("supervisorctl -s http://localhost:9004 stop contrail-discovery:0")
    run("supervisorctl -s http://localhost:9004 stop contrail-schema")
    run("supervisorctl -s http://localhost:9004 stop contrail-svc-monitor")
    run("supervisorctl -s http://localhost:9004 stop redis-config")
    run("supervisorctl -s http://localhost:9004 stop contrail-config-nodemgr")
    run("supervisorctl -s http://localhost:9004 stop ifmap")
    zoo_release = get_release('zookeeper')
    if '3.4.3' in zoo_release and zoo_release != '3.4.3':
        run("supervisorctl -s http://localhost:9004 stop contrail-zookeeper")
    else:
        with settings(warn_only=True):
            if "running" in run("service zookeeper status"):
                run("service zookeeper stop")

    #if detect_ostype() in ['Ubuntu']:
    #    apt_install(['zookeeper'])
    #else:
    #    yum_install(['zookeeper'])
    #with settings(warn_only=True):
    #    #http://mail-archives.apache.org/mod_mbox/zookeeper-dev/201304.mbox/%3C20130408030947.8FD7F5073C@tyr.zones.apache.org%3E
    #    run('/usr/sbin/useradd --comment "ZooKeeper" --shell /bin/bash -r --groups hadoop --home /usr/share/zookeeper zookeeper')

    execute("restore_zookeeper_config_node", env.host_string)
    execute("zoolink_node", env.host_string)

    if '3.4.3' in get_release('zookeeper'):
        run("supervisorctl -s http://localhost:9004 start contrail-zookeeper")
    else:
        run("service zookeeper start")

    #zookeeper_status = {}
    #status_cmd = "zkServer.sh status"
    #if detect_ostype() in ['Ubuntu'] and get_release() not in RELEASES_WITH_ZOO_3_4_3:
    #    status_cmd = '/usr/share/zookeeper/bin/zkServer.sh status'
    #for host_string in env.roledefs['cfgm']:
    #    with settings(host_string=host_string, warn_only=True):
    #        retries = 5
    #        for i in range(retries):
    #            status = run(status_cmd)
    #            if 'Error contacting service' not in status:
    #                break
    #            sleep(2)
    #        for stat in ['leader', 'follower', 'standalone']:
    #            if stat in status:
    #                status = stat
    #                break
    #        zookeeper_status.update({host_string: status})

    #if (len(env.roledefs['cfgm']) == 1):
    #    if 'standalone' in zookeeper_status.values():
    #        print "Zookeeper status is standalone on Single node..ok"
    #    else:
    #        print "Zookeepr status is not standalone on single node..Fix it and retry upgrade"
    #        print zookeeper_status
    #        exit(1)
    #else:
    #    if ('leader' in zookeeper_status.values() and 'standalone' not in zookeeper_status.values()):
    #        print "Zookeeper leader/follower election is done."
    #    else:
    #        print "Zookeepr leader/follower election has problems. Fix it and retry upgrade"
    #        print zookeeper_status
    #        exit(1)

@task
@serial
@roles('cfgm')
def start_api_services():
    with settings(warn_only=True):
        if get_release() in RELEASES_WITH_ZOO_3_4_3:
            run("supervisorctl -s http://localhost:9004 start contrail-zookeeper")
        else:
            run("service zookeeper start")
        run("supervisorctl -s http://localhost:9004 start contrail-config-nodemgr")
        run("supervisorctl -s http://localhost:9004 start ifmap")
        run("supervisorctl -s http://localhost:9004 start redis-config")
        run("supervisorctl -s http://localhost:9004 start contrail-api:0")
        run("supervisorctl -s http://localhost:9004 start contrail-discovery:0")
        run("supervisorctl -s http://localhost:9004 start contrail-svc-monitor")
        run("supervisorctl -s http://localhost:9004 start contrail-schema")


@task
@parallel
@roles('cfgm')
def backup_zookeeper_config():
    execute("backup_zookeeper_config_node", env.host_string)

@task
def backup_zookeeper_config_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if run('ls /etc/zookeeper/zoo.cfg').succeeded:
                zoo_cfg = '/etc/zookeeper/zoo.cfg'
            else:
                zoo_cfg = '/etc/zookeeper/conf/zoo.cfg'
            if not run('ls /etc/contrail/zoo.cfg.rpmsave').succeeded:
                run('cp %s /etc/contrail/zoo.cfg.rpmsave' % zoo_cfg)

@task
@parallel
@roles('cfgm')
def restore_zookeeper_config():
    execute("restore_zookeeper_config_node", env.host_string)

@task
def restore_zookeeper_config_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if run('ls /etc/contrail/zoo.cfg.rpmsave').succeeded:
                if get_release() not in RELEASES_WITH_ZOO_3_4_3:
                    #upgrade to >= 1.05
                    run('cp /etc/contrail/zoo.cfg.rpmsave /etc/zookeeper/conf/zoo.cfg')
                run('rm -f /etc/contrail/zoo.cfg.rpmsave')

@task
@parallel
@roles('cfgm')
def backup_discovery_ini():
    execute("backup_discovery_ini_node", env.host_string)

@task
def backup_discovery_ini_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if (detect_ostype() in ['centos']):
                if run('ls /etc/contrail/supervisord_config_files/contrail-discovery.ini').succeeded:
                    run('cp /etc/contrail/supervisord_config_files/contrail-discovery.ini /etc/contrail/contrail-discovery.ini.save')

@task
@parallel
@roles('cfgm')
def restore_discovery_ini():
    execute("restore_discovery_ini_node", env.host_string)

@task
def restore_discovery_ini_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if (detect_ostype() in ['centos']):
                if run('ls /etc/contrail/contrail-discovery.ini.save').succeeded:
                    run('cp /etc/contrail/contrail-discovery.ini.save /etc/contrail/supervisord_config_files/contrail-discovery.ini')
                    run('rm -f /etc/contrail/contrail-discovery.ini.save')

@task
@EXECUTE_TASK
@roles('database')
def uninstall_database():
    execute("uninstall_database_node", env.host_string)

@task
def uninstall_database_node(*args):
    for host_string in args:
        with  settings(host_string=host_string):
            contrail_database_ver = run("rpm -q --queryformat '%{VERSION}' contrail-database")
            if contrail_database_ver == '1.02':
                execute("stop_database")
                #delete old version, this will erase contrail-database & contrail-openstack-database
                run("yum -y --disablerepo=* --enablerepo=contrail_install_repo erase contrail-database")
                #install new version, this will install contrail-database & contrail-openstack-database
                #start will happen later after update of all other packages
                run('yum -y --disablerepo=* --enablerepo=contrail_install_repo install contrail-openstack-database')
            elif contrail_database_ver == '1.0':
                execute("stop_database")
                #delete old version, 1.0 version the PREUN script does not run and yum erase fails
                #following commands helps overcome that
                run('yum -y --disablerepo=* --enablerepo=contrail_install_repo erase contrail-openstack-database')
                run('rpm --erase --nopreun contrail-database')
                #install new version, start will happen later after update of all other packages
                run('yum -y --disablerepo=* --enablerepo=contrail_install_repo install contrail-openstack-database')

@task
def purge_database_node(*args):
    for host_string in args:
        if detect_ostype() == 'Ubuntu':
            with settings(host_string=host_string, warn_only=True):
                run('apt-get -y  purge contrail-database')
@task
@EXECUTE_TASK
@roles('database')
def purge_database():
    execute('purge_database_node', env.host_string)

@task
def fix_supervisord_config_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if detect_ostype() == 'Ubuntu':
                run('apt-get -y  --reinstall -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install contrail-openstack-config') 
                run('rm /etc/contrail/supervisord_config_files/contrail-zookeeper.ini')

            # config does not use redis anymore
            run('rm -f /etc/contrail/redis_config.conf')
            run('rm -f /etc/contrail/supervisord_config_files/redis-config.ini')

@task
@EXECUTE_TASK
@roles('cfgm')
def fix_supervisord_config():
    execute('fix_supervisord_config_node', env.host_string)

@task
def fix_supervisord_analytics_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                run('apt-get -y --reinstall -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install contrail-openstack-analytics')
@task
@EXECUTE_TASK
@roles('collector')
def fix_supervisord_analytics():
    execute('fix_supervisord_analytics_node', env.host_string)

@task
def fix_supervisord_control_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                run('apt-get -y --reinstall -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install contrail-openstack-control')
@task
@EXECUTE_TASK
@roles('control')
def fix_supervisord_control():
    execute('fix_supervisord_control_node', env.host_string)

@task
@EXECUTE_TASK
@roles('openstack')
def increase_item_size_max():
    """Increases the memcached item_size_max to 2 MB"""
    execute('increase_item_size_max_node', env.host_string)

@task
def increase_item_size_max_node(*args):
    """Increases the memcached item_size_max to 2 MB in one or list of nodes. USAGE:fab increase_item_size_max_node:user@1.1.1.1,user@2.2.2.2"""
    item_size_max = '2m'
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if detect_ostype() == 'Ubuntu':
                memcache_conf='/etc/memcached.conf'
                if run('grep "\-I " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    run('echo "-I %s" >> %s' % (item_size_max, memcache_conf))
            else:
                memcache_conf='/etc/sysconfig/memcached'
                opts = run("grep OPTIONS %s | grep -Po '\".*?\"'" % memcache_conf)
                if opts.failed:
                    #Write option to memcached config file
                    run("echo 'OPTIONS=\"-I %s\"' >> %s" % (item_size_max, memcache_conf))
                elif run("grep OPTIONS %s | grep -Po '\".*?\"' | grep \"\-I\"" % memcache_conf).failed:
                    #concatenate with the existing options
                    opts = opts.strip('"') + '-I %s' % item_size_max
                    run("sed -i 's/OPTIONS.*/OPTIONS=\"%s\"/g' %s" % (opts, memcache_conf))

def yum_upgrade():
    run('yum clean all')
    run('yum -y --disablerepo=* --enablerepo=contrail_install_repo update')

def apt_upgrade():
    execute('backup_source_list')
    execute('create_contrail_source_list')
    run(' apt-get clean')
    rls = get_release()
    if '1.04' in rls:
        #Hack to solve the webui config file issue
        cmd = "yes N | DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes upgrade"
    elif ('1.05' in rls or '1.06' in rls):
        cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confold" update'
        run(cmd)
        cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confold" dist-upgrade'
        run(cmd)
        cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confold" autoremove'
        run(cmd)
        execute('restore_source_list')
        return
    else:
        cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes upgrade"
    run(cmd)
    execute('restore_source_list')
    
@task
def upgrade():
    if detect_ostype() in ['centos', 'fedora']:
        yum_upgrade()
    elif detect_ostype() in ['Ubuntu']:
        apt_upgrade()

@task
def upgrade_api_venv_packages():
    pip_cmd = "pip install -U -I --force-reinstall --no-deps --index-url=''"
    with settings(warn_only=True):
        if run("ls /opt/contrail/api-venv/archive").succeeded:
            run('chmod +x /opt/contrail/api-venv/bin/pip')
            run("source /opt/contrail/api-venv/bin/activate && %s /opt/contrail/api-venv/archive/*" % pip_cmd)

def cleanup_venv(venv):
    if get_build('contrail-%s' % venv) == get_build():
        print "Virtual Enviroinment [contrail-%s] is already cleaned up" % venv
        return
    with settings(warn_only=True):
        venvs = copy.deepcopy(VENVS)
        if env.host_string in env.roledefs['cfgm']:
            venvs.remove('api-venv')
        if env.host_string in env.roledefs['collector']:
            venvs.remove('analytics-venv')
        if venv in venvs:
            with settings(warn_only=True):
                run('rm -rf /opt/contrail/%s' % venv)
                return

        if run("ls /opt/contrail/%s" % venv).succeeded:
            run("rm -rf /opt/contrail/%s/*" % venv)
            run('apt-get -y --reinstall install contrail-%s' % venv)
            if venv == "api-venv":
                run('apt-get -y --reinstall install python-neutronclient contrail-config contrail-config-extension')
            if venv == "analytics-venv":
                run('apt-get -y --reinstall install contrail-analytics')

@task
def cleanup_venvs():
    if detect_ostype() != 'Ubuntu':
        print "No need to clenup venv packages."
        return
    cleanup_venv('api-venv')
    cleanup_venv('analytics-venv')
    cleanup_venv('vrouter-venv')
    cleanup_venv('control-venv')
    cleanup_venv('database-venv')

@task
def upgrade_venv_packages():
    pip_cmd = "pip install -U -I --force-reinstall --no-deps --index-url=''"
    with settings(warn_only=True):
        if run("ls /opt/contrail/api-venv/archive").succeeded:
            run('chmod +x /opt/contrail/api-venv/bin/pip')
            run("source /opt/contrail/api-venv/bin/activate && %s /opt/contrail/api-venv/archive/*" % pip_cmd)
        if run("ls /opt/contrail/analytics-venv/archive").succeeded:
            run('chmod +x /opt/contrail/analytics-venv/bin/pip')
            run("source /opt/contrail/analytics-venv/bin/activate && %s /opt/contrail/analytics-venv/archive/*" % pip_cmd)
        if run("ls /opt/contrail/vrouter-venv/archive").succeeded:
            run('chmod +x /opt/contrail/vrouter-venv/bin/pip')
            run("source /opt/contrail/vrouter-venv/bin/activate && %s /opt/contrail/vrouter-venv/archive/*" % pip_cmd)
        if run("ls /opt/contrail/control-venv/archive").succeeded:
            run('chmod +x /opt/contrail/control-venv/bin/pip')
            run("source /opt/contrail/control-venv/bin/activate && %s /opt/contrail/control-venv/archive/*" % pip_cmd)
        if run("ls /opt/contrail/database-venv/archive").succeeded:
            run('chmod +x /opt/contrail/database-venv/bin/pip')
            run("source /opt/contrail/database-venv/bin/activate && %s /opt/contrail/database-venv/archive/*" % pip_cmd)

@task
@EXECUTE_TASK
@roles('database')
def upgrade_database(pkg):
    """Upgrades the contrail database pkgs in all nodes defined in database."""
    execute("upgrade_database_node", pkg, env.host_string)

@task
def upgrade_database_node(pkg, *args):
    """Upgrades database pkgs in one or list of nodes. USAGE:fab upgrade_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            if detect_ostype() in ['centos', 'fedora']:
                execute('uninstall_database_node', host_string)
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute(upgrade)
            execute(cleanup_venvs)
            execute('purge_database_node', host_string)
            execute(upgrade_venv_packages)
            execute('upgrade_pkgs_node', host_string)
            execute('restart_database_node', host_string)

@task
@roles('openstack')
def fix_nova_conf():
    execute("fix_nova_conf_node", env.host_string)

@task
def fix_nova_conf_node(*args):
    keystone_ip = getattr(testbed, 'keystone_ip', env.roledefs['openstack'][0].split('@')[1])
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            run("openstack-config --del /etc/nova/nova.conf DEFAULT rpc_backend")
            run("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host %s" % keystone_ip)

@task
@EXECUTE_TASK
@roles('openstack')
def upgrade_openstack(pkg):
    """Upgrades openstack pkgs in all nodes defined in openstack role."""
    execute("upgrade_openstack_node", pkg, env.host_string)

@task
def upgrade_openstack_node(pkg, *args):
    """Upgrades openstack pkgs in one or list of nodes. USAGE:fab upgrade_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute(upgrade)
            execute('increase_item_size_max_node', host_string)
            with settings(warn_only=True):
                if get_release() in ['1.05', '1.06']:
                    run('apt-get -y remove openstack-dashboard-ubuntu-theme')
            execute(cleanup_venvs)
            execute(upgrade_api_venv_packages)
            execute('upgrade_pkgs_node', host_string)
            execute('fix_nova_conf_node', host_string)
            execute('setup_contrail_horizon_node', host_string)
            execute('restart_openstack_node', host_string)


@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_cfgm(pkg):
    """Upgrades config pkgs in all nodes defined in cfgm role."""
    execute("upgrade_cfgm_node", pkg, env.host_string)

@task
def upgrade_cfgm_node(pkg, *args):
    """Upgrades config pkgs in one or list of nodes. USAGE:fab upgrade_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_zookeeper_config_node', host_string)
            execute(upgrade)
            execute('upgrade_zookeeper_node', host_string)
            execute(cleanup_venvs)
            execute('fix_supervisord_config_node', host_string)
            execute('restore_zookeeper_config_node', host_string)
            execute(upgrade_venv_packages)
            execute('upgrade_pkgs_node', host_string)


@task
@EXECUTE_TASK
@roles('control')
def upgrade_control(pkg):
    """Upgrades control pkgs in all nodes defined in control role."""
    execute("upgrade_control_node", pkg, env.host_string)

@task
def upgrade_control_node(pkg, *args):
    """Upgrades control pkgs in one or list of nodes. USAGE:fab upgrade_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)

            # If necessary, migrate to new ini format based configuration.
            with settings(warn_only=True):
                if run("ls /etc/contrail/control-node.conf").failed:
                    run("/opt/contrail/contrail_installer/contrail_config_templates/control-node.conf.sh")
                if run("ls /etc/contrail/dns.conf").failed:
                    run("/opt/contrail/contrail_installer/contrail_config_templates/dns.conf.sh")
            execute(upgrade)
            execute(cleanup_venvs)
            execute('fix_supervisord_control_node', host_string)
            execute(upgrade_venv_packages)
            execute('upgrade_pkgs_node', host_string)
            execute('restart_control_node', host_string)


@task
@EXECUTE_TASK
@roles('collector')
def upgrade_collector(pkg):
    """Upgrades analytics pkgs in all nodes defined in collector role."""
    execute("upgrade_collector_node", pkg, env.host_string)

@task
def upgrade_collector_node(pkg, *args):
    """Upgrades analytics pkgs in one or list of nodes. USAGE:fab upgrade_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute(upgrade)
            execute(cleanup_venvs)
            execute('fix_supervisord_analytics_node', host_string)
            execute(upgrade_venv_packages)
            execute('upgrade_pkgs_node', host_string)
            fix_redis_uve_conf()
            fix_vizd_param()
            execute('restart_collector_node', host_string)


@task
@EXECUTE_TASK
@roles('webui')
def upgrade_webui(pkg):
    """Upgrades webui pkgs in all nodes defined in webui role."""
    execute("upgrade_webui_node", pkg, env.host_string)

@task
def upgrade_webui_node(pkg, *args):
    """Upgrades webui pkgs in one or list of nodes. USAGE:fab upgrade_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute(upgrade)
            execute(cleanup_venvs)
            execute(upgrade_venv_packages)
            execute('upgrade_pkgs_node', host_string)
            execute('restart_webui_node', host_string)


@task
@EXECUTE_TASK
@roles('compute')
def upgrade_vrouter(pkg):
    """Upgrades vrouter pkgs in all nodes defined in vrouter role."""
    execute("upgrade_vrouter_node", pkg, env.host_string)

@task
def upgrade_vrouter_node(pkg, *args):
    """Upgrades vrouter pkgs in one or list of nodes. USAGE:fab upgrade_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute(upgrade)
            execute(cleanup_venvs)
            execute(upgrade_venv_packages)
            execute('setup_vrouter_node', host_string)

@task
@EXECUTE_TASK
@roles('all')
def upgrade_all(pkg):
    """Upgrades all the contrail pkgs in all nodes."""
    if detect_ostype() in ['centos', 'fedora']:
        execute(uninstall_database)
    execute(backup_install_repo)
    execute('install_pkg_all', pkg)
    execute(create_install_repo)
    execute(check_and_stop_disable_qpidd_in_openstack)
    execute(check_and_stop_disable_qpidd_in_cfgm)
    execute('stop_collector')
    # needed only for centos all in one box as setup_cfgm is not run.
    execute(backup_discovery_ini)
    execute(upgrade)
    execute(upgrade_zookeeper)
    with settings(warn_only=True):
        if get_release() in ['1.05', '1.06']:
            run('apt-get -y remove openstack-dashboard-ubuntu-theme')
    execute(cleanup_venvs)
    execute(purge_database)
    execute(increase_item_size_max)
    execute(fix_supervisord_config)
    execute(fix_supervisord_analytics)
    execute(fix_supervisord_control)
    execute(upgrade_venv_packages)
    execute(upgrade_pkgs)
    fix_vizd_param()
    fix_redis_uve_conf()
    execute(restart_database)
    execute(fix_nova_conf)
    execute(setup_contrail_horizon)
    execute(restart_openstack)
    execute(restore_zookeeper_config)
    # needed only for centos all in one box as setup_cfgm is not run.
    execute(restore_discovery_ini)
    execute(restart_cfgm)
    execute(restart_control)
    execute(restart_collector)
    execute(restart_webui)
    execute(setup_vrouter)
    with settings(host_string=env.roledefs['compute'][0]):
        if detect_ostype() in ['Ubuntu']:
            execute(rmmod_vrouter)
    execute(create_default_secgrp_rules)
    execute(compute_reboot)
    #Clear the connections cache
    connections.clear()
    execute(restart_openstack_compute)

@roles('build')
@task
def upgrade_contrail(pkg):
    """Upgrades all the  contrail packages in all nodes as per the role definition.
    """
    execute('check_and_kill_zookeeper')
    execute(backup_zookeeper_config)
    if len(env.roledefs['all']) == 1:
        execute('upgrade_all', pkg)
    else:
        execute('install_pkg_all', pkg)
        execute(check_and_stop_disable_qpidd_in_openstack)
        execute(check_and_stop_disable_qpidd_in_cfgm)
        execute('upgrade_cfgm', pkg)
        execute('start_zookeeper')
        execute(check_and_setup_rabbitmq_cluster)
        execute('setup_cfgm')
        execute('start_api_services')
        execute('upgrade_database', pkg)
        execute('stop_collector')
        execute('upgrade_collector', pkg)
        execute('upgrade_openstack', pkg)
        execute('upgrade_control', pkg)
        execute('upgrade_webui', pkg)
        execute('upgrade_vrouter', pkg)
        execute('fixup_agent_param')
        with settings(host_string=env.roledefs['compute'][0]):
            if detect_ostype() in ['Ubuntu']:
                execute(rmmod_vrouter)
        execute(create_default_secgrp_rules)
        execute(compute_reboot)
        #Clear the connections cache
        connections.clear()
        execute(restart_openstack_compute)


@roles('build')
@task
def upgrade_without_openstack(pkg):
    """Upgrades all the  contrail packages in all nodes except openstack node as per the role definition.
    """
    execute('check_and_kill_zookeeper')
    execute(backup_zookeeper_config)
    execute('install_pkg_all', pkg)
    execute(check_and_stop_disable_qpidd_in_cfgm)
    execute('upgrade_cfgm', pkg)
    execute('start_zookeeper')
    execute(check_and_setup_rabbitmq_cluster)
    execute(setup_cfgm)
    execute('start_api_services')
    execute('upgrade_database', pkg)
    execute('upgrade_collector', pkg)
    execute('upgrade_control', pkg)
    execute('upgrade_webui', pkg)
    execute('upgrade_vrouter', pkg)
    execute('fixup_agent_param')
    with settings(host_string=env.roledefs['compute'][0]):
        if detect_ostype() in ['Ubuntu']:
            execute(rmmod_vrouter)
    execute(create_default_secgrp_rules)
    execute(compute_reboot)
    #Clear the connections cache
    connections.clear()
    execute(restart_openstack_compute)

@task
@EXECUTE_TASK
@roles('all')
def backup_install_repo():
    """Backup contrail install repo in all nodes."""
    execute("backup_install_repo_node", env.host_string)

@task
def backup_install_repo_node(*args):
    """Backup contrail install repo in one or list of nodes. USAGE:fab create_install_repo_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            version = run("cat /opt/contrail/contrail_packages/VERSION | cut -d '=' -f2")
            version = version.strip()
            out = run("ls /opt/contrail/")
            if 'contrail_install_repo_%s' % version not in out:
                run("mv /opt/contrail/contrail_install_repo /opt/contrail/contrail_install_repo_%s" % version)

@task
@hosts(env.roledefs['cfgm'][0])
def check_and_setup_rabbitmq_cluster():
    if get_release() not in RELEASES_WITH_QPIDD:
        execute(setup_rabbitmq_cluster)

@task
@EXECUTE_TASK
@roles('openstack')
def check_and_stop_disable_qpidd_in_openstack():
    if (get_release('contrail-openstack') in RELEASES_WITH_QPIDD and
        get_release() not in RELEASES_WITH_QPIDD):
        execute('stop_and_disable_qpidd_node', env.host_string)

@task
@EXECUTE_TASK
@roles('cfgm')
def check_and_stop_disable_qpidd_in_cfgm():
    if (get_release('contrail-openstack-config') in RELEASES_WITH_QPIDD and
        get_release() not in RELEASES_WITH_QPIDD):
        execute('stop_and_disable_qpidd_node', env.host_string)

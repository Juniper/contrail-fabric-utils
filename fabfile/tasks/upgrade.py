import os
import copy

from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.config import *
from fabfile.tasks.helpers import insert_line_to_file

# Upgrade data from 1.05 to 1.10
R1_05_TO_R1_10 = {
    'openstack' : {'upgrade'       : ['contrail-openstack'],
                   'remove'        : [],
                   'install'       : ['supervisor=1:3.0a8-1.2'],
                   'backup_files'  : [],
                   'remove_files'  : [],
                  },
    'database'  : {'upgrade'       : ['contrail-openstack-database'],
                   'remove'        : [],
                   'install'       : ['supervisor=1:3.0a8-1.2'],
                   'backup_files'  : [],
                   'remove_files'  : [],
                  },
    'cfgm'      : {'upgrade'       : ['contrail-openstack-config'],
                   'remove'        : ['contrail-api-venv',
                                      'contrail-config-extension',
                                      'contrail-libs'],
                   'install'       : ['ifmap-server=0.3.2-1contrail1',
                                      'rabbitmq-server=3.3.2-1',
                                      'euca2ools=1:2.1.3-2',
                                      'supervisor=1:3.0a8-1.2',
                                      'python-boto=1:2.12.0'],
                   'backup_files'  : ['/etc/contrail/discovery.conf',
                                      '/etc/contrail/vnc_api_lib.ini'],
                   'remove_files'  : [],
                  },
    'collector' : {'upgrade'       : ['contrail-openstack-analytics'],
                   'remove'        : ['contrail-analytics-venv'],
                   'install'       : ['supervisor=1:3.0a8-1.2'],
                   'backup_files'  : [],
                   'remove_files'  : ['/etc/contrail/supervisord_analytics_files/redis-*.ini'],
                  },
    'control'   : {'upgrade'       : ['contrail-openstack-control'],
                   'remove'        : [],
                   'install'       : ['supervisor=1:3.0a8-1.2',
                                      'python-redis=2.8.0-1contrail1'],
                   'backup_files'  : [],
                   'remove_files'  : [],
                  },
    'webui'     : {'upgrade'       : ['contrail-openstack-webui'],
                   'remove'        : ['contrail-webui',
                                      'contrail-nodejs'],
                   'install'       : ['supervisor=1:3.0a8-1.2'],
                   'backup_files'  : [],
                   'remove_files'  : [],
                  },
    'compute'   : {'upgrade'       : ['contrail-openstack-vrouter'],
                   'remove'        : ['contrail-vrouter'],
                   'install'       : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'remove_files'  : [],
                  },
}

# Upgrade data for upgrade from 1.05 to 1.10 mainline
R1_05_TO_R1_10main = R1_05_TO_R1_10
# Upgrade data for upgrade from 1.06 to 1.10 mainline
R1_06_TO_R1_10main = R1_05_TO_R1_10
# Upgrade data for upgrade from 1.06 to R1.10
R1_06_TO_R1_10 = R1_05_TO_R1_10

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

def upgrade_package(pkgs, ostype):
    if ostype in ['centos', 'fedora']:
        run('yum clean all')
        for pkg in pkgs:
            run('yum -y --disablerepo=* --enablerepo=contrail_install_repo install %s' % pkg)
    elif ostype in ['Ubuntu']:
        execute('backup_source_list')
        execute('create_contrail_source_list')
        run(' apt-get clean')
        for pkg in pkgs:
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install %s' % pkg
            run(cmd)
        execute('restore_source_list')
        return
    
@task
@EXECUTE_TASK
@roles('all')
def backup_config(from_rel):
    ostype = detect_ostype()
    to_rel = get_release()
    try:
        upgrade_data = eval(('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
    except NameError:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))
    run('mkdir -p /tmp/contrail')
    for role in upgrade_data.keys():
        if env.host_string in env.roledefs[role]:
            with settings(warn_only=True):
                for config_file in upgrade_data[role]['backup_files']:
                    cfg_file_name = os.path.basename(config_file)
                    if run('cp %s /tmp/contrail/%s.upgradesave' % (config_file, cfg_file_name)).failed:
                        if not files.exists('/tmp/contrail/%s.upgradesave' % cfg_file_name):
                            raise RuntimeError("Unable to backup config file %s, please correct and continue upgrade." % config_file)

def restore_config(role, upgrade_data):
    for config_file in upgrade_data[role]['backup_files']:
        cfg_file_name = os.path.basename(config_file)
        run('cp /tmp/contrail/%s.upgradesave %s' % (cfg_file_name, config_file))

def install_package(pkgs, ostype):
    for pkg in pkgs:
        if ostype in ['centos', 'fedora']:
            run('yum -y --disablerepo=* --enablerepo=contrail_install_repo install %s' % pkg)
        elif ostype in ['Ubuntu']:
            run('DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install %s' % pkg)

def remove_package(pkgs, ostype):
    with settings(warn_only=True):
        for pkg in pkgs:
            if ostype in ['centos', 'fedora']:
                run('yum -y --disablerepo=* --enablerepo=contrail_install_repo erase %s' % pkg)
            elif ostype in ['Ubuntu']:
                run('DEBIAN_FRONTEND=noninteractive apt-get -y remove --purge  %s' % pkg)

def remove_old_files(role, upgrade_data):
    with settings(warn_only=True):
        for config_file in upgrade_data[role]['remove_files']:
            run("rm %s" % config_file)

def upgrade(from_rel, role):
    ostype = detect_ostype()
    to_rel = get_release()
    try:
        upgrade_data = eval(('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
    except NameError:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))
    #backup_config(role, upgrade_data)
    install_package(upgrade_data[role]['install'], ostype)
    upgrade_package(upgrade_data[role]['upgrade'], ostype)
    remove_package(upgrade_data[role]['remove'], ostype)
    restore_config(role, upgrade_data)
    remove_old_files(role, upgrade_data)

@task
def testing():
    upgrade('contrail-openstack')

@task
@EXECUTE_TASK
@roles('database')
def upgrade_database(from_rel, pkg):
    """Upgrades the contrail database pkgs in all nodes defined in database."""
    execute("upgrade_database_node", from_rel, pkg, env.host_string)

@task
def upgrade_database_node(from_rel, pkg, *args):
    """Upgrades database pkgs in one or list of nodes. USAGE:fab upgrade_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'database')
            execute('upgrade_pkgs_node', host_string)
            # Required to setup zookeeper in database node and create database nodemgr conf
            execute('setup_database_node', host_string)
            execute('restart_database_node', host_string)

@task
@roles('openstack')
def fix_nova_conf():
    execute("fix_nova_conf_node", env.host_string)

@task
def fix_nova_conf_node(*args):
    rabbit_host = get_openstack_amqp_server()
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            run("openstack-config --del /etc/nova/nova.conf DEFAULT rpc_backend")
            run("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host %s" % rabbit_host)

@task
@EXECUTE_TASK
@roles('openstack')
def upgrade_openstack(from_rel, pkg):
    """Upgrades openstack pkgs in all nodes defined in openstack role."""
    execute("upgrade_openstack_node", from_rel, pkg, env.host_string)

@task
def upgrade_openstack_node(from_rel, pkg, *args):
    """Upgrades openstack pkgs in one or list of nodes. USAGE:fab upgrade_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'openstack')
            execute('increase_item_size_max_node', host_string)
            execute('upgrade_pkgs_node', host_string)
            execute('restart_openstack_node', host_string)

@task
@EXECUTE_TASK
@roles('cfgm')
def fix_discovery_conf():
    cassandra_ip_list = [hstr_to_ip(get_control_host_string(cassandra_host)) for cassandra_host in env.roledefs['database']]
    cassandra_srv_list = 'cassandra_server_list=' + ':9160'.join(cassandra_ip_list) + ':9160'
    run('sed -i "/\[DEFAULTS\]/a\%s" /etc/contrail/discovery.conf' % cassandra_srv_list)

@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_cfgm(from_rel, pkg):
    """Upgrades config pkgs in all nodes defined in cfgm role."""
    execute("upgrade_cfgm_node", from_rel, pkg, env.host_string)

@task
def upgrade_cfgm_node(from_rel, pkg, *args):
    """Upgrades config pkgs in one or list of nodes. USAGE:fab upgrade_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('stop_cfgm_node', host_string)
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'cfgm')
            execute('upgrade_pkgs_node', host_string)

@task
@EXECUTE_TASK
@roles('control')
def upgrade_control(from_rel, pkg):
    """Upgrades control pkgs in all nodes defined in control role."""
    execute("upgrade_control_node", from_rel, pkg, env.host_string)

@task
def upgrade_control_node(from_rel, pkg, *args):
    """Upgrades control pkgs in one or list of nodes. USAGE:fab upgrade_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'control')
            execute('upgrade_pkgs_node', host_string)
            # If necessary, migrate to new ini format based configuration.
            run("/opt/contrail/contrail_installer/contrail_config_templates/control-node.conf.sh")
            run("/opt/contrail/contrail_installer/contrail_config_templates/dns.conf.sh")
            execute('restart_control_node', host_string)


@task
@EXECUTE_TASK
@roles('collector')
def upgrade_collector(from_rel, pkg):
    """Upgrades analytics pkgs in all nodes defined in collector role."""
    execute("upgrade_collector_node", from_rel, pkg, env.host_string)

@task
def upgrade_collector_node(from_rel, pkg, *args):
    """Upgrades analytics pkgs in one or list of nodes. USAGE:fab upgrade_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'collector')
            execute('upgrade_pkgs_node', host_string)
            # If necessary, migrate to new ini format based configuration.
            run("/opt/contrail/contrail_installer/contrail_config_templates/collector.conf.sh")
            execute('restart_collector_node', host_string)


@task
@EXECUTE_TASK
@roles('webui')
def upgrade_webui(from_rel, pkg):
    """Upgrades webui pkgs in all nodes defined in webui role."""
    execute("upgrade_webui_node", from_rel, pkg, env.host_string)

@task
def upgrade_webui_node(from_rel, pkg, *args):
    """Upgrades webui pkgs in one or list of nodes. USAGE:fab upgrade_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'webui')
            execute('upgrade_pkgs_node', host_string)
            execute('restart_webui_node', host_string)


@task
@EXECUTE_TASK
@roles('compute')
def upgrade_vrouter(from_rel, pkg):
    """Upgrades vrouter pkgs in all nodes defined in vrouter role."""
    execute("upgrade_vrouter_node", from_rel, pkg, env.host_string)

@task
def upgrade_vrouter_node(from_rel, pkg, *args):
    """Upgrades vrouter pkgs in one or list of nodes. USAGE:fab upgrade_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'compute')
            import pdb; pdb.set_trace()
            # If necessary, migrate to new ini format based configuration.
            run("/opt/contrail/contrail_installer/contrail_config_templates/vrouter-agent.conf.sh")

@task
@EXECUTE_TASK
@roles('compute')
def fix_vrouter_configs():
    """Fix the vrouter config files as per 1.10 standard"""
    execute("fix_vrouter_configs_node", env.host_string)

@task
def fix_vrouter_configs_node(*args):
    """Fix the vrouter config files as per 1.10 standard in one or list of nodes. USAGE:fab fix_vrouter_configs_node:user@1.1.1.1,user@2.2.2.2"""
    with settings(warn_only=True):
        if_vhost0 = run('grep "pre-up /opt/contrail/bin/if-vhost0" /etc/network/interfaces')
    if if_vhost0.failed:
        run('sed -i "/iface vhost0 inet static/a\    pre-up /opt/contrail/bin/if-vhost0" /etc/network/interfaces')
    agent_param = '/etc/contrail/agent_param'
    # Replace the vrouter binary name
    old_prog = '^prog=/usr/bin/vnswad'
    new_prog = 'prog=/usr/bin/contrail-vrouter-agent'
    insert_line_to_file(pattern=old_prog, line=new_prog, file_name=agent_param)

    # Replace the vrouter process name
    old_pname = '^pname=vnswad'
    new_pname = 'pname=contrail-vrouter-agent'
    insert_line_to_file(pattern=old_pname, line=new_pname, file_name=agent_param)

    # Replace the vrouter kernal module
    old_kmod = '^kmod=.*'
    new_kmod = 'kmod=vrouter'
    insert_line_to_file(pattern=old_kmod, line=new_kmod, file_name=agent_param)

@task
@roles('build')
def upgrade_contrail(from_rel, pkg):
    """Upgrades all the contrail pkgs in all nodes."""
    execute('install_pkg_all', pkg)
    #execute('zookeeper_rolling_restart')
    execute('fix_discovery_conf')
    execute('backup_config', from_rel)
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    execute('setup_rabbitmq_cluster', True)
    execute('restart_cfgm')
    execute('upgrade_collector', from_rel, pkg)
    execute('upgrade_control', from_rel, pkg)
    execute('upgrade_webui', from_rel, pkg)
    execute('fix_vrouter_configs')
    execute('upgrade_vrouter', from_rel, pkg)
    execute('create_default_secgrp_rules')
    execute('compute_reboot')
    #Clear the connections cache
    connections.clear()
    execute('restart_openstack_compute')

@task
@roles('build')
def upgrade_without_openstack(pkg):
    """Upgrades all the  contrail packages in all nodes except openstack node as per the role definition.
    """
    execute('install_pkg_all', pkg)
    #execute('zookeeper_rolling_restart')
    execute('backup_config')
    execute('fix_discovery_conf')
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    execute('setup_rabbitmq_cluster')
    execute('restart_cfgm')
    execute('upgrade_collector', from_rel, pkg)
    execute('upgrade_control', from_rel, pkg)
    execute('upgrade_webui', from_rel, pkg)
    execute('fix_vrouter_configs')
    execute('upgrade_vrouter', from_rel, pkg)
    execute('create_default_secgrp_rules')
    execute('compute_reboot')
    #Clear the connections cache
    connections.clear()
    execute('restart_openstack_compute')

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

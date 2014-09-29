import os
import copy

from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.config import *
from fabfile.tasks.helpers import insert_line_to_file

# upgrade schema
UPGRADE_SCHEMA = {
    'openstack' : {'upgrade' : ['contrail-openstack'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : [],
                   'backup_dirs' : ['/etc/keystone',
                                    '/etc/glance',
                                    '/etc/nova',
                                    '/etc/cinder',
                                   ],
                   'remove_files' : [],
                  },
    'database' : {'upgrade' : ['contrail-openstack-database'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/database_nodemgr_param',
                                     '/etc/contrail/contrail-nodemgr-database.conf',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : [],
                  },
    'cfgm' : {'upgrade' : ['contrail-openstack-config'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/svc_monitor.conf',
                                     '/etc/contrail/schema_transformer.conf',
                                     '/etc/contrail/contrail-api.conf',
                                     '/etc/contrail/contrail-discovery.conf',
                                     '/etc/contrail/vnc_api_lib.ini',
                                    ],
                   'backup_dirs' : ['/etc/ifmap-server',
                                    '/etc/neutron',
                                   ],
                   'remove_files' : [],
                  },
    'collector' : {'upgrade' : ['contrail-openstack-analytics'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/contrail-analytics-api.conf',
                                     '/etc/contrail/contrail-collector.conf',
                                     '/etc/contrail/contrail-query-engine.conf',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : [],
                  },
    'control' : {'upgrade' : ['contrail-openstack-control'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/contrail-control.conf',
                                     '/etc/contrail/dns.conf'],
                   'backup_dirs' : [],
                   'remove_files' : [],
                  },
    'webui' : {'upgrade' : ['contrail-openstack-webui'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/config.global.js'],
                   'backup_dirs' : [],
                   'remove_files' : [],
                  },
    'compute' : {'upgrade' : ['contrail-openstack-vrouter'],
                   'remove' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/agent_param',
                                     '/etc/contrail/contrail-vrouter-agent.conf',
                                     '/etc/contrail/vrouter_nodemgr_param',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : [],
                  },
}

if get_openstack_internal_vip():
    ha_backup_dirs = ['/etc/mysql', '/etc/keepalived', '/etc/contrail/ha']
    UPGRADE_SCHEMA['openstack']['backup_dirs'] += ha_backup_dirs
    UPGRADE_SCHEMA['openstack']['upgrade'].append('contrail-openstack-ha')

# Upgrade data from 1.05 to 1.10
UBUNTU_R1_05_TO_R1_10 = {
    'openstack' : {'upgrade'       : ['contrail-openstack'],
                   'remove'        : [],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'database'  : {'upgrade'       : ['contrail-openstack-database'],
                   'remove'        : [],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'cfgm'      : {'upgrade'       : ['contrail-openstack-config'],
                   'remove'        : ['contrail-api-venv',
                                      'contrail-config-extension',
                                      'contrail-libs',
                                      'zookeeper'],
                   'downgrade'     : ['ifmap-server=0.3.2-1contrail1',
                                      'python-contrail',
                                      'rabbitmq-server>=3.3.2-1',
                                      'euca2ools=1:2.1.3-2',
                                      'supervisor=1:3.0a8-1.2',
                                      'python-boto=1:2.12.0',
                                      'python-six=1.5.2-1~cloud0'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/rabbitmq/rabbitmq.config'],
                  },
    'collector' : {'upgrade'       : ['contrail-openstack-analytics'],
                   'remove'        : ['contrail-analytics-venv'],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/contrail/supervisord_analytics_files/redis-*.ini',
                                      '/etc/contrail/supervisord_analytics_files/contrail-qe.ini',
                                      '/etc/contrail/supervisord_analytics_files/contrail-opserver.ini'],
                  },
    'control'   : {'upgrade'       : ['contrail-openstack-control'],
                   'remove'        : [],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-redis=2.8.0-1contrail1',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'webui'     : {'upgrade'       : ['contrail-openstack-webui'],
                   'remove'        : ['contrail-webui',
                                      'contrail-nodejs'],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],

                   'backup_files'  : ['/etc/contrail/config.global.js'],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'compute'   : {'upgrade'       : ['contrail-openstack-vrouter'],
                   'remove'        : ['contrail-vrouter'],
                   'downgrade'     : ['supervisor=1:3.0a8-1.2',
                                      'python-contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/contrail/supervisord_vrouter_files/contrail-vrouter.ini'],
                  },
}

# Upgrade data for upgrade from 1.06 to R1.10
UBUNTU_R1_06_TO_R1_10 = copy.deepcopy(UBUNTU_R1_05_TO_R1_10)
UBUNTU_R1_06_TO_R1_10['compute']['backup_files'].append('/etc/contrail/contrail-vrouter-agent.conf')
UBUNTU_R1_06_TO_R1_20 = copy.deepcopy(UBUNTU_R1_06_TO_R1_10)
# In Release upgrade
UBUNTU_R1_10_TO_R1_10 = copy.deepcopy(UPGRADE_SCHEMA)
UBUNTU_R1_10_TO_R1_20 = copy.deepcopy(UPGRADE_SCHEMA)
UBUNTU_R1_20_TO_R1_20 = copy.deepcopy(UPGRADE_SCHEMA)

# Upgrade data from 1.05 to 1.10(Centos)
CENTOS_R1_05_TO_R1_10 = {
    'openstack' : {'upgrade'       : ['contrail-openstack'],
                   'remove'        : ['supervisor',
                                      'python-pycassa',
                                      'openstack-dashboard',
                                      'contrail-openstack-dashboard',
                                      'python-boto',
                                      'python-neutronclient',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python'],
                   'downgrade'     : ['supervisor',
                                      'openstack-dashboard',
                                      'contrail-openstack-dashboard',
                                      'python-pycassa',
                                      'python-boto',
                                      'python-neutronclient',
                                      'python-bitarray',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'database'  : {'upgrade'       : ['contrail-openstack-database'],
                   'remove'        : ['supervisor',
                                      'contrail-api-venv',
                                      'contrail-database-venv',
                                      'contrail-analytics-venv',
                                      'contrail-control-venv',
                                      'contrail-vrouter-venv',
                                      'xmltodict',
                                      'python-bitarray',
                                      'python-oauth2'],
                   'downgrade'     : ['python-contrail',
                                      'xmltodict',
                                      'python-bitarray',
                                      'supervisor'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'cfgm'      : {'upgrade'       : ['contrail-openstack-config'],
                   'remove'        : ['supervisor',
                                      'contrail-api-venv',
                                      'contrail-database-venv',
                                      'contrail-analytics-venv',
                                      'contrail-control-venv',
                                      'contrail-vrouter-venv',
                                      'euca2ools',
                                      'python-boto',
                                      'python-thrift',
                                      'python-lxml',
                                      'python-neutronclient',
                                      'xmltodict',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'python-zope-filesystem',
                                      'python-zope-interface',
                                      'contrail-config-extension',
                                      'contrail-libs',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python',
                                      'irond',
                                      'openstack-neutron-contrail',
                                      'python-pycassa'],
                   'downgrade'     : ['supervisor',
                                      'python-pycassa',
                                      'euca2ools',
                                      'python-boto',
                                      'python-thrift',
                                      'python-lxml',
                                      'python-neutronclient',
                                      'python-zope-interface',
                                      'xmltodict',
                                      'python-bitarray',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python',
                                      'irond-1.0-2contrail'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/rabbitmq/rabbitmq.config'],
                  },
    'collector' : {'upgrade'       : ['contrail-openstack-analytics'],
                   'remove'        : ['supervisor',
                                      'contrail-api-venv',
                                      'contrail-database-venv',
                                      'contrail-analytics-venv',
                                      'contrail-control-venv',
                                      'contrail-analytics-venv',
                                      'xmltodict',
                                      'redis-py',
                                      'python-thrift',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'python-pycassa'],
                   'downgrade'     : ['supervisor',
                                      'python-pycassa',
                                      'redis-py',
                                      'xmltodict',
                                      'python-thrift',
                                      'python-bitarray'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/contrail/supervisord_analytics_files/redis-*.ini',
                                      '/etc/contrail/supervisord_analytics_files/contrail-qe.ini',
                                      '/etc/contrail/supervisord_analytics_files/contrail-opserver.ini'],
                  },
    'control'   : {'upgrade'       : ['contrail-openstack-control'],
                   'remove'        : ['supervisor',
                                      'python-pycassa',
                                      'xmltodict',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'python-thrift',
                                      'contrail-api-venv',
                                      'contrail-database-venv',
                                      'contrail-analytics-venv',
                                      'contrail-control-venv',
                                      'contrail-vrouter-venv'],
                   'downgrade'     : ['supervisor',
                                      'python-pycassa',
                                      'xmltodict',
                                      'python-thrift',
                                      'python-bitarray'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'webui'     : {'upgrade'       : ['contrail-openstack-webui'],
                   'remove'        : ['supervisor',
                                      'contrail-webui',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'python-thrift',
                                      'contrail-nodejs'],
                   'downgrade'     : ['supervisor',
                                      'python-thrift',
                                      'python-bitarray'],
                   'backup_files'  : ['/etc/contrail/config.global.js'],
                   'backup_dirs' : [],
                   'remove_files'  : [],
                  },
    'compute'   : {'upgrade'       : ['contrail-openstack-vrouter'],
                   'remove'        : ['supervisor',
                                      'python-pycassa',
                                      'python-boto',
                                      'python-thrift',
                                      'python-neutronclient',
                                      'xmltodict',
                                      'python-bitarray',
                                      'python-oauth2',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python',
                                      'contrail-api-venv',
                                      'contrail-database-venv',
                                      'contrail-analytics-venv',
                                      'contrail-control-venv',
                                      'contrail-vrouter-venv'],
                   'downgrade'     : ['supervisor',
                                      'python-pycassa',
                                      'python-boto',
                                      'python-thrift',
                                      'python-neutronclient',
                                      'xmltodict',
                                      'python-bitarray',
                                      'libvirt-client',
                                      'libvirt',
                                      'libvirt-python'],
                   'backup_files'  : [],
                   'backup_dirs' : [],
                   'remove_files'  : ['/etc/contrail/supervisord_vrouter_files/contrail-vrouter.ini']
                  },
}

CENTOS_UPGRADE_SCHEMA = copy.deepcopy(UPGRADE_SCHEMA)
# Add contrail-interface-name to upgrade list if interface rename enabled.
if getattr(env, 'interface_rename', True):
    CENTOS_R1_05_TO_R1_10['compute']['upgrade'].append('contrail-interface-name')
    CENTOS_UPGRADE_SCHEMA['compute']['upgrade'].append('contrail-interface-name')

# In Release upgrade
CENTOS_R1_10_TO_R1_10 = copy.deepcopy(CENTOS_UPGRADE_SCHEMA)
CENTOS_R1_10_TO_R1_20 = copy.deepcopy(CENTOS_UPGRADE_SCHEMA)
CENTOS_R1_10_TO_R1_20['cfgm']['backup_dirs'].remove('/etc/ifmap-server')
CENTOS_R1_10_TO_R1_20['cfgm']['backup_dirs'].append('/etc/irond')
CENTOS_R1_20_TO_R1_20 = copy.deepcopy(CENTOS_R1_10_TO_R1_20)

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
def backup_config_dir(from_rel):
    ostype = detect_ostype()
    to_rel = get_release()
    try:
        upgrade_data = eval(ostype.upper() + '_' + ('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
    except NameError:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))
    for role in upgrade_data.keys():
        if env.host_string in env.roledefs[role]:
            with settings(warn_only=True):
                for config_dir in upgrade_data[role]['backup_dirs']:
                    cfg_dir_name = os.path.basename(config_dir)
                    run('mkdir -p /tmp/contrail/%s.upgradesave' % cfg_dir_name)
                    if run('cp -r %s/* /tmp/contrail/%s.upgradesave' % (config_dir, cfg_dir_name)).failed:
                        if not files.exists('/tmp/contrail/%s.upgradesave' % cfg_dir_name):
                            raise RuntimeError("Unable to backup config dir %s, please correct and continue upgrade." % config_dir)

def restore_config_dir(role, upgrade_data):
    for config_dir in upgrade_data[role]['backup_dirs']:
        cfg_dir_name = os.path.basename(config_dir)
        run('cp -r /tmp/contrail/%s.upgradesave/* %s' % (cfg_dir_name, config_dir))

@task
@EXECUTE_TASK
@roles('all')
def backup_config(from_rel):
    ostype = detect_ostype()
    to_rel = get_release()
    try:
        upgrade_data = eval(ostype.upper() + '_' + ('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
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

def downgrade_package(pkgs, ostype):
    for pkg in pkgs:
        if ostype in ['centos', 'fedora']:
            run('yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail_install_repo install %s' % pkg)
        elif ostype in ['Ubuntu']:
            run('DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install %s' % pkg)

def remove_package(pkgs, ostype):
    with settings(warn_only=True):
        for pkg in pkgs:
            if pkg == 'zookeeper' and env.host_string in env.roledefs['database']:
                print "need not remove zookeeper, cfgm and database in same nodes."
                return
            if ostype in ['centos', 'fedora']:
                run('rpm -e --nodeps %s' % pkg)
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
        upgrade_data = eval(ostype.upper() + '_' + ('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
    except NameError:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))
    #backup_config(role, upgrade_data)
    if ostype == 'centos':
        #buildid = get_build('contrail-setup')
        remove_package(upgrade_data[role]['remove'], ostype)
        #downgrade_package(['supervisor-0.1-%s' % buildid], ostype)
    downgrade_package(upgrade_data[role]['downgrade'], ostype)
    upgrade_package(upgrade_data[role]['upgrade'], ostype)
    if ostype == 'Ubuntu':
        remove_package(upgrade_data[role]['remove'], ostype)
    restore_config(role, upgrade_data)
    restore_config_dir(role, upgrade_data)
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
            if from_rel in ['1.05', '1.06']:
                # Required to setup zookeeper in database node and create database nodemgr conf
                execute('setup_database_node', host_string)
                execute('restart_database_node', host_string)
            else:
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
    execute('add_openstack_reserverd_ports')
    execute("upgrade_openstack_node", from_rel, pkg, env.host_string)

@task
def upgrade_openstack_node(from_rel, pkg, *args):
    """Upgrades openstack pkgs in one or list of nodes. USAGE:fab upgrade_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    openstack_services = ['openstack-nova-api', 'openstack-nova-scheduler', 'openstack-nova-cert',
                          'openstack-nova-consoleauth', 'openstack-nova-novncproxy',
                          'openstack-nova-conductor', 'openstack-nova-compute']
    if detect_ostype() in ['Ubuntu']:
        openstack_services = ['nova-api', 'nova-scheduler', 'glance-api',
                              'glance-registry', 'keystone',
                              'nova-conductor', 'cinder-api', 'cinder-scheduler']
    for host_string in args:
        with settings(host_string=host_string):
            for svc in openstack_services:
                with settings(warn_only=True):
                    run("service %s stop" % svc)
            execute('backup_install_repo_node', host_string)
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            upgrade(from_rel, 'openstack')
            execute('increase_item_size_max_node', host_string)
            execute('upgrade_pkgs_node', host_string)
            # Set the rabbit_host as from 1.10 the rabbit listens at the control_data ip
            amqp_server_ip = get_openstack_amqp_server()
            run("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host %s" % amqp_server_ip)
            run("openstack-config --set /etc/glance/glance-api.conf DEFAULT rabbit_host %s" % amqp_server_ip)
            execute('restart_openstack_node', host_string)

@task
@roles('cfgm')
def fix_rabbitmq_conf():
    rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
    run("rm -rf %s" % rabbit_conf)
    amqp_listen_ip = get_openstack_amqp_server()
    run('sudo echo "[" >> %s' % rabbit_conf)
    run("sudo echo '   {rabbit, [ {tcp_listeners, [{\"%s\", 5672}]},' >> %s" % (amqp_listen_ip, rabbit_conf))
    run('sudo echo "   {loopback_users, []}," >> %s' % rabbit_conf)
    run('sudo echo "   {log_levels,[{connection, info},{mirroring, info}]} ]" >> %s' % rabbit_conf)
    run('sudo echo "    }" >> %s' % rabbit_conf)
    run('sudo echo "]." >> %s' % rabbit_conf)

@task
@EXECUTE_TASK
@roles('cfgm')
def stop_rabbitmq():
    run("service rabbitmq-server stop")

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
            if len(env.roledefs['cfgm']) == 1:
                execute('fix_rabbitmq_conf')
            execute('upgrade_pkgs_node', host_string)

@task
@serial
@roles('control')
def upgrade_control(from_rel, pkg):
    """Upgrades control pkgs in all nodes defined in control role."""
    with settings(warn_only=True):
        execute('stop_control_node', env.host_string)
    execute("upgrade_control_node", from_rel, pkg, env.host_string)
    execute('restart_control_node', env.host_string)

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
            if from_rel in ['1.05', '1.06']:
                execute('setup_control_node', host_string)
            else:
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
            if from_rel in ['1.05', '1.06']:
                execute('setup_collector_node', host_string)
            else:
                execute('restart_collector_node', host_string)


@task
def fix_config_global_js_node(*args):
    new_config = """
config.featurePkg = {};
/* Add new feature Package Config details below */
config.featurePkg.webController = {};
config.featurePkg.webController.path = '/usr/src/contrail/contrail-web-controller';
config.featurePkg.webController.enable = true;

/******************************************************************************
 * Boolean flag getDomainProjectsFromApiServer indicates wheather the project
 * list should come from API Server or Identity Manager.
 * If Set
 *      - true, then project list will come from API Server
 *      - false, then project list will come from Identity Manager
 * Default: false
 *
******************************************************************************/
config.getDomainProjectsFromApiServer = false;
/*****************************************************************************
* Boolean flag L2_enable indicates the default forwarding-mode of a network.
* Allowed values : true / false
* Set this flag to true if all the networks are to be L2 networks,
* set to false otherwise.
*****************************************************************************/
config.network = {};
config.network.L2_enable = false;
// Export this as a module.
module.exports = config;
"""
    for host_string in args:
        with settings(host_string=host_string):
            run("sed -i '$d' /etc/contrail/config.global.js")
            run("sed -i '$d' /etc/contrail/config.global.js")
            run("echo \"%s\" >> /etc/contrail/config.global.js" % new_config)
            # Make sure juniper logo is set
            logo_old = '/usr/src/contrail/contrail-webui/webroot/img/juniper-networks-logo.png';
            logo_new = '/usr/src/contrail/contrail-web-core/webroot/img/juniper-networks-logo.png';
            run("sed -i 's#%s#%s#g' /etc/contrail/config.global.js" % (logo_old, logo_new))
            logo_old = '/usr/src/contrail/contrail-web-core/webroot/img/opencontrail-logo.png';
            run("sed -i 's#%s#%s#g' /etc/contrail/config.global.js" % (logo_old, logo_new))

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
            if from_rel in ['1.05', '1.06']:
                execute('fix_config_global_js_node', host_string)
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
            # If necessary, migrate to new ini format based configuration.
            if from_rel == '1.05':
                run("/opt/contrail/contrail_installer/contrail_config_templates/vrouter-agent.conf.sh")
            if detect_ostype() in ['centos']:
                execute('setup_vrouter_node', host_string)

@task
@EXECUTE_TASK
@roles('compute')
def fix_vrouter_configs():
    """Fix the vrouter config files as per 1.10 standard"""
    execute("fix_vrouter_configs_node", env.host_string)

@task
def fix_vrouter_configs_node(*args):
    """Fix the vrouter config files as per 1.10 standard in one or list of nodes. USAGE:fab fix_vrouter_configs_node:user@1.1.1.1,user@2.2.2.2"""
    ostype = detect_ostype()
    if ostype in ['Ubuntu']:
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
    if ostype in ['Ubuntu']:
        old_kmod = '^kmod=.*'
        new_kmod = 'kmod=vrouter'
        insert_line_to_file(pattern=old_kmod, line=new_kmod, file_name=agent_param)

@task
@roles('build')
def upgrade_contrail(from_rel, pkg):
    """Upgrades all the contrail pkgs in all nodes."""
    execute('install_pkg_all', pkg)
    execute('zookeeper_rolling_restart')
    execute('backup_config', from_rel)
    execute('backup_config_dir', from_rel)
    execute('stop_rabbitmq')
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    if from_rel in ['1.05', '1.06']:
        execute('setup_rabbitmq_cluster', True)
        execute('setup_cfgm')
    else:
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
@roles('build')
def upgrade_without_openstack(pkg):
    """Upgrades all the  contrail packages in all nodes except openstack node as per the role definition.
    """
    execute('install_pkg_all', pkg)
    execute('zookeeper_rolling_restart')
    execute('backup_config', from_rel)
    execute('backup_config_dir', from_rel)
    execute('stop_rabbitmq')
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    if from_rel in ['1.05', '1.06']:
        execute('setup_rabbitmq_cluster', True)
        execute('setup_cfgm')
    else:
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

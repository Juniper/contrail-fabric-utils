import os
import sys
import copy
import string

from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.utils.cluster import is_lbaas_enabled
from fabfile.config import *
from fabfile.tasks.helpers import insert_line_to_file
from fabfile.tasks.provision import fixup_restart_haproxy_in_all_cfgm

# upgrade schema
UPGRADE_SCHEMA = {
    'openstack' : {'upgrade' : ['contrail-openstack'],
                   'remove' : [],
                   'ensure' : [],
                   'downgrade' : [],
                   'backup_files' : [],
                   'backup_dirs' : ['/etc/keystone',
                                    '/etc/glance',
                                    '/etc/nova',
                                    '/etc/cinder',
                                   ],
                   'remove_files' : [],
                   'rename_files' : [],
                  },
    'database' : {'upgrade' : ['contrail-openstack-database'],
                   'remove' : [],
                   'ensure' : [],
                   'downgrade' : [],
                   'backup_files' : ['/etc/contrail/database_nodemgr_param',
                                     '/etc/contrail/contrail-nodemgr-database.conf',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : ['/etc/init/supervisord-contrail-database.conf',
                                     '/etc/contrail/supervisord_contrail_database.conf',
                                    ],
                   'rename_files' : [('/etc/contrail/contrail-nodemgr-database.conf',
                                      '/etc/contrail/contrail-database-nodemgr.conf'),],
                  },
    'cfgm' : {'upgrade' : ['contrail-openstack-config'],
                   'remove' : [],
                   'downgrade' : [],
                   'ensure' : [],
                   'backup_files' : ['/etc/contrail/svc_monitor.conf',
                                     '/etc/contrail/schema_transformer.conf',
                                     '/etc/contrail/contrail-api.conf',
                                     '/etc/contrail/contrail-discovery.conf',
                                     '/etc/contrail/vnc_api_lib.ini',
                                     '/etc/init.d/contrail-api',
                                     '/etc/init.d/contrail-discovery'
                                    ],
                   'backup_dirs' : ['/etc/ifmap-server',
                                    '/etc/neutron',
                                   ],
                   'remove_files' : ['/etc/contrail/supervisord_config_files/rabbitmq-server.ini'],
                   'rename_files' : [],
                  },
    'collector' : {'upgrade' : ['contrail-openstack-analytics'],
                   'remove' : [],
                   'downgrade' : [],
                   'ensure' : [],
                   'backup_files' : ['/etc/contrail/contrail-analytics-api.conf',
                                     '/etc/contrail/contrail-collector.conf',
                                     '/etc/contrail/contrail-query-engine.conf',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : [],
                   'rename_files' : [],
                  },
    'control' : {'upgrade' : ['contrail-openstack-control'],
                   'remove' : [],
                   'downgrade' : [],
                   'ensure' : [],
                   'backup_files' : ['/etc/contrail/contrail-control.conf',
                                     '/etc/contrail/dns.conf'],
                   'backup_dirs' : [],
                   'remove_files' : ['/var/log/named/bind.log',
                                     '/etc/contrail/dns/dns.conf'
                                    ],
                   'rename_files' : [('/etc/contrail/dns.conf', '/etc/contrail/contrail-dns.conf'),
                                     ('/etc/contrail/dns/named.conf',
                                      '/etc/contrail/dns/contrail-named.conf'),
                                     ('/etc/contrail/dns/rndc.conf',
                                      '/etc/contrail/dns/contrail-rndc.conf'),
                                     ('/etc/contrail/dns/named.pid',
                                      '/etc/contrail/dns/contrail-named.pid'),
                                    ],
                  },
    'webui' : {'upgrade' : ['contrail-openstack-webui'],
                   'remove' : [],
                   'downgrade' : [],
                   'ensure' : [],
                   'backup_files' : ['/etc/contrail/config.global.js'],
                   'backup_dirs' : [],
                   'remove_files' : [],
                   'rename_files' : [],
                  },
    'compute' : {'upgrade' : ['contrail-openstack-vrouter'],
                   'remove' : [],
                   'downgrade' : [],
                   'ensure' : [],
                   'backup_files' : ['/etc/contrail/agent_param',
                                     '/etc/contrail/contrail-vrouter-agent.conf',
                                     '/etc/contrail/vrouter_nodemgr_param',
                                     '/etc/nova/nova.conf',
                                    ],
                   'backup_dirs' : [],
                   'remove_files' : [],
                   'rename_files' : [],
                  },
}

if get_openstack_internal_vip():
    ha_backup_dirs = ['/etc/mysql', '/etc/keepalived', '/etc/contrail/ha']
    UPGRADE_SCHEMA['openstack']['backup_dirs'] += ha_backup_dirs
    UPGRADE_SCHEMA['openstack']['upgrade'].append('contrail-openstack-ha')

# Ubuntu Release upgrade
UBUNTU_R1_10_TO_R2_10 = copy.deepcopy(UPGRADE_SCHEMA)
UBUNTU_R1_20_TO_R2_10 = copy.deepcopy(UPGRADE_SCHEMA)
UBUNTU_R1_21_TO_R2_10 = copy.deepcopy(UBUNTU_R1_20_TO_R2_10)
UBUNTU_R1_30_TO_R2_10 = copy.deepcopy(UPGRADE_SCHEMA)
UBUNTU_R1_30_TO_R2_10['cfgm']['backup_files'].remove('/etc/contrail/svc_monitor.conf')
UBUNTU_R1_30_TO_R2_10['cfgm']['backup_files'].remove('/etc/contrail/schema_transformer.conf')
UBUNTU_R1_30_TO_R2_10['cfgm']['backup_files'] += ['/etc/contrail/contrail-svc-monitor.conf',
                                                 '/etc/contrail/contrail-schema.conf']
UBUNTU_R1_30_TO_R2_10['database']['backup_files'].remove('/etc/contrail/contrail-nodemgr-database.conf')
UBUNTU_R1_30_TO_R2_10['database']['backup_files'].append('/etc/contrail/contrail-database-nodemgr.conf')
UBUNTU_R2_0_TO_R2_10 = copy.deepcopy(UBUNTU_R1_30_TO_R2_10)
UBUNTU_R2_0_TO_R2_10['database']['rename_files'].remove(('/etc/contrail/contrail-nodemgr-database.conf',
                                                        '/etc/contrail/contrail-database-nodemgr.conf'))
UBUNTU_R2_0_TO_R2_10['control']['backup_files'].remove('/etc/contrail/dns.conf')
UBUNTU_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns.conf',
                                                        '/etc/contrail/contrail-dns.conf'))
UBUNTU_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/named.conf',
                                                        '/etc/contrail/dns/contrail-named.conf'))
UBUNTU_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/rndc.conf',
                                                        '/etc/contrail/dns/contrail-rndc.conf'))
UBUNTU_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/named.pid',
                                                        '/etc/contrail/dns/contrail-named.pid'))
UBUNTU_R2_10_TO_R2_10 = copy.deepcopy(UBUNTU_R2_0_TO_R2_10)

CENTOS_UPGRADE_SCHEMA = copy.deepcopy(UPGRADE_SCHEMA)
# Add contrail-interface-name to upgrade list if interface rename enabled.
if getattr(env, 'interface_rename', True):
    CENTOS_UPGRADE_SCHEMA['compute']['upgrade'].append('contrail-interface-name')
libvirt_pkgs = [('libvirt', '0.10.2-{BUILD}'),
                ('libvirt-client', '0.10.2-{BUILD}'),
                ('libvirt-python', '0.10.2-{BUILD}')]
CENTOS_UPGRADE_SCHEMA['openstack']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['openstack']['ensure'] += libvirt_pkgs
CENTOS_UPGRADE_SCHEMA['openstack']['upgrade'] += ['openstack-dashboard']
CENTOS_UPGRADE_SCHEMA['openstack']['rename_files'] += [('/etc/contrail/supervisord_openstack.conf.rpmnew',
                                                        '/etc/contrail/supervisord_openstack.conf')]
CENTOS_UPGRADE_SCHEMA['cfgm']['remove'] += ['contrail-api-extension', 'irond']
CENTOS_UPGRADE_SCHEMA['cfgm']['ensure'] += libvirt_pkgs
CENTOS_UPGRADE_SCHEMA['cfgm']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['database']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['collector']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['control']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['compute']['ensure'] += libvirt_pkgs
CENTOS_UPGRADE_SCHEMA['compute']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['webui']['ensure'] += [('supervisor', '3.0-9.2')]
CENTOS_UPGRADE_SCHEMA['webui']['rename_files'] += [('/etc/contrail/supervisord_webui.conf.rpmnew',
                                                        '/etc/contrail/supervisord_webui.conf')]

# Centos Release upgrade
CENTOS_R1_10_TO_R2_10 = copy.deepcopy(CENTOS_UPGRADE_SCHEMA)
CENTOS_R1_10_TO_R2_10['cfgm']['backup_dirs'].remove('/etc/ifmap-server')
CENTOS_R1_10_TO_R2_10['cfgm']['backup_dirs'].append('/etc/irond')
CENTOS_R1_10_TO_R2_10['cfgm']['rename_files'].append((
    '/etc/irond/authorization.properties',
    '/etc/ifmap-server/authorization.properties'))
CENTOS_R1_10_TO_R2_10['cfgm']['rename_files'].append((
    '/etc/irond/basicauthusers.properties',
    '/etc/ifmap-server/basicauthusers.properties'))
CENTOS_R1_20_TO_R2_10 = copy.deepcopy(CENTOS_R1_10_TO_R2_10)
CENTOS_R1_21_TO_R2_10 = copy.deepcopy(CENTOS_R1_20_TO_R2_10)
CENTOS_R2_0_TO_R2_10 = copy.deepcopy(CENTOS_UPGRADE_SCHEMA)
CENTOS_R2_0_TO_R2_10['cfgm']['backup_files'].remove('/etc/contrail/svc_monitor.conf')
CENTOS_R2_0_TO_R2_10['cfgm']['backup_files'].append('/etc/contrail/contrail-svc-monitor.conf')
CENTOS_R2_0_TO_R2_10['cfgm']['backup_files'].remove('/etc/contrail/schema_transformer.conf')
CENTOS_R2_0_TO_R2_10['cfgm']['backup_files'].append('/etc/contrail/contrail-schema.conf')
CENTOS_R2_0_TO_R2_10['database']['backup_files'].remove('/etc/contrail/contrail-nodemgr-database.conf')
CENTOS_R2_0_TO_R2_10['database']['backup_files'].append('/etc/contrail/contrail-database-nodemgr.conf')
CENTOS_R2_0_TO_R2_10['database']['rename_files'].remove(('/etc/contrail/contrail-nodemgr-database.conf',
                                                        '/etc/contrail/contrail-database-nodemgr.conf'))
CENTOS_R2_0_TO_R2_10['control']['backup_files'].remove('/etc/contrail/dns.conf')
CENTOS_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns.conf',
                                                        '/etc/contrail/contrail-dns.conf'))
CENTOS_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/named.conf',
                                                        '/etc/contrail/dns/contrail-named.conf'))
CENTOS_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/rndc.conf',
                                                        '/etc/contrail/dns/contrail-rndc.conf'))
CENTOS_R2_0_TO_R2_10['control']['rename_files'].remove(('/etc/contrail/dns/named.pid',
                                                        '/etc/contrail/dns/contrail-named.pid'))
CENTOS_R2_10_TO_R2_10 = copy.deepcopy(CENTOS_R2_0_TO_R2_10)

def format_upgrade_schema(data, **formater):
    if type(data) is dict:
        for key, value in data.items():
            data[key] = format_upgrade_schema(value, **formater)
        return data
    elif type(data) is list:
        for elem in data:
            data.remove(elem)
            data.append(format_upgrade_schema(elem, **formater))
        return data
    elif type(data) is tuple:
        dummy = list(data)
        for elem in data:
            dummy.remove(elem)
            dummy.append(format_upgrade_schema(elem, **formater))
        data = tuple(dummy)
        return data
    elif type(data) is str:
        return data.format(**formater)

def get_upgrade_schema(ostype, from_rel, to_rel, build):
    try:
        upgrade_schema = eval(ostype.upper() + '_' + ('R'+from_rel+'_TO_'+'R'+to_rel).replace('.','_'))
    except NameError:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))
    formater = {'BUILD': build}
    return format_upgrade_schema(upgrade_schema, **formater)

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
            version = sudo("cat /opt/contrail/contrail_packages/VERSION | cut -d '=' -f2")
            version = version.strip()
            out = sudo("ls /opt/contrail/")
            if 'contrail_install_repo_%s' % version not in out:
                sudo("mv /opt/contrail/contrail_install_repo /opt/contrail/contrail_install_repo_%s" % version)

@task
def backup_source_list():
    sudo('mv /etc/apt/sources.list /etc/apt/sources.list.upgradesave')

@task
def create_contrail_source_list():
    sudo('echo "deb file:/opt/contrail/contrail_install_repo ./" > /etc/apt/sources.list')
@task
def restore_source_list():
    with settings(warn_only=True):
        sudo('mv /etc/apt/sources.list.upgradesave /etc/apt/sources.list')

def fix_vizd_param():
    if sudo('ls /etc/contrail/vizd_param').succeeded:
        sudo('grep -q ANALYTICS_SYSLOG_PORT /etc/contrail/vizd_param || echo "ANALYTICS_SYSLOG_PORT=-1" >> /etc/contrail/vizd_param')

@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_zookeeper():
    execute('upgrade_zookeeper_node', env.host_string)

@task
def upgrade_zookeeper_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                print "No need to upgrade specifically zookeeper in ubuntu."
                return
            with settings(warn_only=True):
                sudo('rpm -e --nodeps zookeeper zookeeper-lib zkpython')
            yum_install(['zookeeper'])
            sudo('yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail_install_repo reinstall contrail-config')
            sudo('chkconfig zookeeper on')

@task
@parallel
@roles('cfgm')
def backup_zookeeper_config():
    execute("backup_zookeeper_config_node", env.host_string)

@task
def backup_zookeeper_config_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if sudo('ls /etc/zookeeper/zoo.cfg').succeeded:
                zoo_cfg = '/etc/zookeeper/zoo.cfg'
            else:
                zoo_cfg = '/etc/zookeeper/conf/zoo.cfg'
            if not sudo('ls /etc/contrail/zoo.cfg.rpmsave').succeeded:
                sudo('cp %s /etc/contrail/zoo.cfg.rpmsave' % zoo_cfg)

@task
@parallel
@roles('cfgm')
def restore_zookeeper_config():
    execute("restore_zookeeper_config_node", env.host_string)

@task
def restore_zookeeper_config_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if sudo('ls /etc/contrail/zoo.cfg.rpmsave').succeeded:
                if get_release() not in RELEASES_WITH_ZOO_3_4_3:
                    #upgrade to >= 1.05
                    sudo('cp /etc/contrail/zoo.cfg.rpmsave /etc/zookeeper/conf/zoo.cfg')
                sudo('rm -f /etc/contrail/zoo.cfg.rpmsave')

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
            if detect_ostype() == 'ubuntu':
                memcache_conf='/etc/memcached.conf'
                if sudo('grep "\-I " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    sudo('echo "-I %s" >> %s' % (item_size_max, memcache_conf))
            else:
                memcache_conf='/etc/sysconfig/memcached'
                opts = sudo("grep OPTIONS %s | grep -Po '\".*?\"'" % memcache_conf)
                if opts.failed:
                    #Write option to memcached config file
                    sudo("echo 'OPTIONS=\"-I %s\"' >> %s" % (item_size_max, memcache_conf))
                elif sudo("grep OPTIONS %s | grep -Po '\".*?\"' | grep \"\-I\"" % memcache_conf).failed:
                    #concatenate with the existing options
                    opts = opts.strip('"') + '-I %s' % item_size_max
                    sudo("sed -i 's/OPTIONS.*/OPTIONS=\"%s\"/g' %s" % (opts, memcache_conf))

def upgrade_package(pkgs, ostype):
    if ostype in ['centos', 'fedora']:
        sudo('yum clean all')
        for pkg in pkgs:
            sudo('yum -y --disablerepo=* --enablerepo=contrail_install_repo install %s' % pkg)
    elif ostype in ['ubuntu']:
        execute('backup_source_list')
        execute('create_contrail_source_list')
        sudo(' apt-get clean')
        for pkg in pkgs:
            cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install %s' % pkg
            sudo(cmd)
        execute('restore_source_list')
        return
    
@task
@EXECUTE_TASK
@roles('all')
def backup_config_dir(from_rel):
    ostype = detect_ostype()
    to_rel = get_release()
    to_build = get_build().split('~')[0]
    upgrade_data = get_upgrade_schema(ostype, from_rel, to_rel, to_build)
    for role in upgrade_data.keys():
        if env.host_string in env.roledefs[role]:
            with settings(warn_only=True):
                for config_dir in upgrade_data[role]['backup_dirs']:
                    cfg_dir_name = os.path.basename(config_dir)
                    if files.exists('/var/tmp/contrail/%s.upgradesave' % cfg_dir_name):
                        print "Already the config dir %s is backed up." % cfg_dir_name
                        continue
                    sudo('mkdir -p /var/tmp/contrail/%s.upgradesave' % cfg_dir_name)
                    if sudo('cp -r %s/* /var/tmp/contrail/%s.upgradesave' % (config_dir, cfg_dir_name)).failed:
                        if not files.exists('/var/tmp/contrail/%s.upgradesave' % cfg_dir_name):
                            raise RuntimeError("Unable to backup config dir %s, please correct and continue upgrade." % config_dir)

def restore_config_dir(role, upgrade_data):
    for config_dir in upgrade_data[role]['backup_dirs']:
        cfg_dir_name = os.path.basename(config_dir)
        sudo('mkdir -p %s' % config_dir)
        sudo('cp -r /var/tmp/contrail/%s.upgradesave/* %s' % (cfg_dir_name, config_dir))

@task
@EXECUTE_TASK
@roles('all')
def backup_config(from_rel):
    ostype = detect_ostype()
    to_rel = get_release()
    to_build = get_build().split('~')[0]
    upgrade_data = get_upgrade_schema(ostype, from_rel, to_rel, to_build)
    sudo('mkdir -p /var/tmp/contrail')
    for role in upgrade_data.keys():
        if env.host_string in env.roledefs[role]:
            with settings(warn_only=True):
                for config_file in upgrade_data[role]['backup_files']:
                    cfg_file_name = os.path.basename(config_file)
                    if files.exists('/var/tmp/contrail/%s.upgradesave' % cfg_file_name):
                        print "Already the config file %s is backed up." % cfg_file_name
                        continue
                    if sudo('cp %s /var/tmp/contrail/%s.upgradesave' % (config_file, cfg_file_name)).failed:
                        if not files.exists('/var/tmp/contrail/%s.upgradesave' % cfg_file_name):
                            raise RuntimeError("Unable to backup config file %s, please correct and continue upgrade." % config_file)

def restore_config(role, upgrade_data):
    for config_file in upgrade_data[role]['backup_files']:
        cfg_file_name = os.path.basename(config_file)
        sudo('cp /var/tmp/contrail/%s.upgradesave %s' % (cfg_file_name, config_file))

def downgrade_package(pkgs, ostype):
    for pkg in pkgs:
        if ostype in ['centos', 'fedora']:
            sudo('yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail_install_repo install %s' % pkg)
        elif ostype in ['ubuntu']:
            sudo('DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install %s' % pkg)

def remove_package(pkgs, ostype):
    with settings(warn_only=True):
        for pkg in pkgs:
            if pkg == 'zookeeper' and env.host_string in env.roledefs['database']:
                print "need not remove zookeeper, cfgm and database in same nodes."
                return
            if ostype in ['centos', 'fedora']:
                sudo('rpm -e --nodeps %s' % pkg)
            elif ostype in ['ubuntu']:
                sudo('DEBIAN_FRONTEND=noninteractive apt-get -y remove --purge  %s' % pkg)

def ensure_package(pkg_versions, ostype):
    with settings(warn_only=True):
        for pkg, version in pkg_versions:
            if ('%s-%s' % (get_release(pkg), get_build(pkg)) == version):
                continue
            else:
                remove_package([pkg], ostype)
                downgrade_package([pkg], ostype)

def remove_old_files(role, upgrade_data):
    with settings(warn_only=True):
        for config_file in upgrade_data[role]['remove_files']:
            sudo("rm -f %s" % config_file)

def rename_files(role, upgrade_data):
    with settings(warn_only=True):
        for old_conf_file, new_conf_file in upgrade_data[role]['rename_files']:
            sudo("mv %s %s" % (old_conf_file, new_conf_file))

def upgrade(from_rel, role):
    ostype = detect_ostype()
    to_rel = get_release()
    to_build = get_build().split('~')[0]
    upgrade_data = get_upgrade_schema(ostype, from_rel, to_rel, to_build)
    #backup_config(role, upgrade_data)
    if ostype == 'centos':
        #buildid = get_build('contrail-setup')
        remove_package(upgrade_data[role]['remove'], ostype)
        #downgrade_package(['supervisor-0.1-%s' % buildid], ostype)
    ensure_package(upgrade_data[role]['ensure'], ostype)
    downgrade_package(upgrade_data[role]['downgrade'], ostype)
    upgrade_package(upgrade_data[role]['upgrade'], ostype)
    if ostype == 'ubuntu':
        remove_package(upgrade_data[role]['remove'], ostype)
    restore_config(role, upgrade_data)
    restore_config_dir(role, upgrade_data)
    rename_files(role, upgrade_data)
    remove_old_files(role, upgrade_data)

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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            if get_release('contrail-openstack-database') in ['1.10', '1.20', '1.21']:
                sudo("service supervisord-contrail-database stop")
            upgrade(from_rel, 'database')
            execute('upgrade_pkgs_node', host_string)
            if from_rel in ['1.05', '1.06']:
                # Required to setup zookeeper in database node and create database nodemgr conf
                execute('setup_database_node', host_string)
                execute('restart_database_node', host_string)
            else:
                sudo('chkconfig supervisor-database on')
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
            sudo("openstack-config --del /etc/nova/nova.conf DEFAULT rpc_backend")
            sudo("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host %s" % rabbit_host)

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
    ostype = detect_ostype()
    for host_string in args:
        with settings(host_string=host_string):
            with settings(warn_only=True):
                sudo("service supervisor-openstack stop")
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            upgrade(from_rel, 'openstack')
            sku = get_build().split('~')[1]
            if from_rel not in ['1.05', '1.06']:
                # Workaround for bug https://bugs.launchpad.net/juniperopenstack/+bug/1383927
                if ostype in ['ubuntu'] and 'juno' not in sku:
                    rel = get_release('contrail-openstack')
                    buildid = get_build('contrail-openstack')
                    if from_rel in ['1.10', '1.20', '1.21']:
                        downgrade_package(['contrail-openstack-dashboard=%s-%s' % (rel, buildid)], ostype)
                    else:
                        upgrade_package(['contrail-openstack-dashboard'], ostype)
                if ostype in ['centos'] and 'havana' in sku:
                    upgrade_package(['contrail-openstack-dashboard'], ostype)
            execute('increase_item_size_max_node', host_string)
            execute('upgrade_pkgs_node', host_string)
            # Set the rabbit_host as from 1.10 the rabbit listens at the control_data ip
            amqp_server_ip = get_openstack_amqp_server()
            sudo("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_host %s" % amqp_server_ip)
            sudo("openstack-config --set /etc/glance/glance-api.conf DEFAULT rabbit_host %s" % amqp_server_ip)
            if get_openstack_internal_vip():
                execute('fixup_restart_haproxy_in_openstack_node', host_string)
            if ostype == 'centos' and from_rel in ['1.20']:
                sudo("sed -i 's#/tmp/supervisor_openstack.sock#/tmp/supervisord_openstack.sock#g' /etc/contrail/supervisord_openstack.conf")
            if from_rel in ['1.20', '1.21'] and 'icehouse' in sku:
                SERVICE_TOKEN = get_service_token()
                OPENSTACK_INDEX = env.roledefs['openstack'].index(host_string) + 1
                sudo('grep -q SERVICE_TOKEN %s || echo "SERVICE_TOKEN=%s" >> %s'
                      % ('/etc/contrail/ctrl-details', SERVICE_TOKEN, '/etc/contrail/ctrl-details'))
                sudo('grep -q OPENSTACK_INDEX %s || echo "OPENSTACK_INDEX=%s" >> %s'
                      % ('/etc/contrail/ctrl-details', OPENSTACK_INDEX, '/etc/contrail/ctrl-details'))
                sudo("/opt/contrail/bin/heat-server-setup.sh")
            execute('restart_openstack_node', host_string)

@task
@roles('cfgm')
def fix_rabbitmq_conf():
    rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
    sudo("rm -rf %s" % rabbit_conf)
    amqp_listen_ip = get_openstack_amqp_server()
    sudo('sudo echo "[" >> %s' % rabbit_conf)
    sudo("sudo echo '   {rabbit, [ {tcp_listeners, [{\"%s\", 5672}]},' >> %s" % (amqp_listen_ip, rabbit_conf))
    sudo('sudo echo "   {loopback_users, []}," >> %s' % rabbit_conf)
    sudo('sudo echo "   {log_levels,[{connection, info},{mirroring, info}]} ]" >> %s' % rabbit_conf)
    sudo('sudo echo "    }" >> %s' % rabbit_conf)
    sudo('sudo echo "]." >> %s' % rabbit_conf)

@task
@EXECUTE_TASK
@roles('cfgm')
def stop_rabbitmq():
    sudo("service rabbitmq-server stop")
    with settings(warn_only=True):
        if get_release('contrail-openstack-config') == '1.10':
            sudo("service supervisor-config stop")
        else:
            sudo("service supervisor-support-service stop")

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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            upgrade(from_rel, 'cfgm')
            with settings(warn_only=True):
                execute('restart_cfgm_node', host_string)
                sudo('supervisorctl -s unix:///tmp/supervisord_config.sock stop all')
                sudo('supervisorctl -s unix:///tmp/supervisord_config.sock reread')
                sudo('supervisorctl -s unix:///tmp/supervisord_config.sock update')
                execute('stop_cfgm_node', host_string)
            sudo('chkconfig supervisor-support-service on')
            if from_rel in ['1.10', '1.20', '1.21', '2.0']:
                with settings(warn_only=True):
                    sudo("kill -9 $(ps ax | grep irond.jar | grep -v grep | awk '{print $1}')")
                if detect_ostype() == 'centos':
                    sudo("rm -rf /etc/irond/")
            if len(env.roledefs['cfgm']) == 1:
                execute('fix_rabbitmq_conf')
            if get_contrail_internal_vip():
                execute('fixup_restart_haproxy_in_collector_node', host_string)
            execute('upgrade_pkgs_node', host_string)
            # Populate the new SCHEDULER section in svc_monitor.conf
            conf_file = '/etc/contrail/svc_monitor.conf'
            if get_release() == '2.10':
                 conf_file = '/etc/contrail/contrail-svc-monitor.conf'
            lbaas_svc_instance_params = {'analytics_server_ip' : hstr_to_ip(env.roledefs['collector'][0]),
                                         'analytics_server_port' : '8081'
                                        }
            for param, value in lbaas_svc_instance_params.items():
                sudo("openstack-config --set %s SCHEDULER %s %s" % (conf_file, param, value))
            if from_rel in ['1.10', '1.20', '1.30', '1.21']:
                # Create Keystone auth config ini
                api_conf_file = '/etc/contrail/contrail-api.conf'
                conf_file = '/etc/contrail/contrail-keystone-auth.conf'
                with settings(warn_only=True):
                    if sudo('grep "\[KEYSTONE\]" %s' % api_conf_file).succeeded:
                        sudo("sed -n -e '/\[KEYSTONE\]/,$p' %s > %s" % (api_conf_file, conf_file))
                # delete [KEYSTONE] section from config files
                sudo("openstack-config --set %s DEFAULTS log_file /var/log/contrail/contrail-api.log" % api_conf_file)
                sudo("openstack-config --del %s KEYSTONE" % api_conf_file)
                sudo("openstack-config --set %s DEFAULTS log_local 1" % api_conf_file)
                sudo("openstack-config --set %s DEFAULTS log_level SYS_NOTICE" % api_conf_file)
                conf_file = '/etc/contrail/contrail-schema.conf'
                sudo("mv /etc/contrail/schema_transformer.conf %s" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_file /var/log/contrail/contrail-schema.log" % conf_file)
                sudo("openstack-config --del %s KEYSTONE" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_level SYS_NOTICE" % conf_file)
                conf_file = '/etc/contrail/contrail-svc-monitor.conf'
                sudo("mv /etc/contrail/svc_monitor.conf %s" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_file /var/log/contrail/contrail-svc-monitor.log" % conf_file)
                sudo("openstack-config --del %s KEYSTONE" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_level SYS_NOTICE" % conf_file)
                conf_file = '/etc/contrail/contrail-discovery.conf'
                sudo("openstack-config --set %s DEFAULTS log_file /var/log/contrail/contrail-discovery.log" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_local True" % conf_file)
                sudo("openstack-config --set %s DEFAULTS log_level SYS_NOTICE" % conf_file)
                # Fix init.d scripts
                sudo("sed -i 's#http://localhost:9004#unix:///tmp/supervisord_config.sock#g' /etc/init.d/contrail-api")
                sudo("sed -i 's#http://localhost:9004#unix:///tmp/supervisord_config.sock#g' /etc/init.d/contrail-discovery")
            fixup_device_manager_config(host_string)

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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            upgrade(from_rel, 'control')
            execute('upgrade_pkgs_node', host_string)
            if from_rel in ['1.10', '1.20', '1.30', '1.21']:
                conf_file = '/etc/contrail/contrail-control.conf'
                #Removing the preceeding empty spaces
                sudo("sed -i 's/^\s\+//g' %s" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
                conf_file = '/etc/contrail/contrail-dns.conf'
                #Removing the preceeding empty spaces
                sudo("sed -i 's/^\s\+//g' %s" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_file /var/log/contrail/contrail-dns.log" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            upgrade(from_rel, 'collector')
            execute('upgrade_pkgs_node', host_string)
            if from_rel in ['1.10', '1.20', '1.30', '1.21']:
                conf_file = '/etc/contrail/contrail-collector.conf'
                sudo("sed -i 's/^\s\+//g' %s" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_file /var/log/contrail/contrail-collector.log" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
                conf_file = '/etc/contrail/contrail-query-engine.conf'
                sudo("sed -i 's/^\s\+//g' %s" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_file /var/log/contrail/contrail-query-engine.log" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
                conf_file = '/etc/contrail/contrail-analytics-api.conf'
                sudo("sed -i 's/^\s\+//g' %s" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
            execute('restart_collector_node', host_string)


@task
def fix_config_global_js_node(*args, **kwargs):
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
            if kwargs['from_rel'] in ['1.05', '1.06']:
                sudo("sed -i '$d' /etc/contrail/config.global.js")
                sudo("sed -i '$d' /etc/contrail/config.global.js")
                sudo("echo \"%s\" >> /etc/contrail/config.global.js" % new_config)
            else:
                # Make sure redis port is changed
                sudo("sed -i s'/6383/6379/g' /etc/contrail/config.global.js")
                # Make sure juniper logo is set
                sudo("sed -i 's#opencontrail#juniper-networks#g' /etc/contrail/config.global.js")

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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            upgrade(from_rel, 'webui')
            execute('upgrade_pkgs_node', host_string)
            execute('fix_config_global_js_node', host_string, from_rel=from_rel)
            if detect_ostype() == 'centos':
                execute('start_redis_webui_node', host_string)
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
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            execute('backup_config', from_rel)
            execute('backup_config_dir', from_rel)
            execute("fix_vrouter_configs_node", host_string)
            upgrade(from_rel, 'compute')
            ostype = detect_ostype()
            if is_lbaas_enabled():
                if (ostype == 'ubuntu'):
                    sudo("apt-get -o Dpkg::Options::='--force-confold' install -y haproxy iproute")
                if (ostype == 'centos'):
                    sudo("yum -y --disablerepo=* --enablerepo=contrail_install_repo install haproxy iproute")
            # Populate new params of contrail-vrouter-agent config file
            conf_file = '/etc/contrail/contrail-vrouter-agent.conf'
            lbaas_svc_instance_params = {'netns_command' : '/usr/bin/opencontrail-vrouter-netns',
                                        }
            for param, value in lbaas_svc_instance_params.items():
                sudo("openstack-config --set %s SERVICE-INSTANCE %s %s" % (conf_file, param, value))
            if from_rel in ['1.10', '1.20', '1.30', '1.21']:
                sudo("openstack-config --set %s DEFAULT log_file /var/log/contrail/contrail-vrouter-agent.log" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_local 1" % conf_file)
                sudo("openstack-config --set %s DEFAULT log_level SYS_NOTICE" % conf_file)
            if ostype in ['centos']:
                execute('setup_vrouter_node', host_string)
                if is_lbaas_enabled():
                    sudo('groupadd -f nogroup')
                    sudo("sed -i s/'Defaults    requiretty'/'#Defaults    requiretty'/g /etc/sudoers")

            # Upgrade nova parameters in nova.conf in compute host from 2.0 to 2.1
            if get_openstack_internal_vip() and from_rel in ['2.0']:
                nova_conf_file = '/etc/nova/nova.conf'
                openstack_compute_service = 'openstack-nova-compute'
                if (ostype == 'ubuntu'):
                    openstack_compute_service = 'nova-compute'
                sudo("service %s stop" % openstack_compute_service)
                sudo("openstack-config --set /etc/nova/nova.conf DEFAULT rpc_response_timeout 30")
                sudo("openstack-config --set /etc/nova/nova.conf DEFAULT report_interval 15")
                sudo("service %s start" % openstack_compute_service)
            execute('reboot_node', 'no', host_string)

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
    if ostype in ['ubuntu']:
        with settings(warn_only=True):
            if_vhost0 = sudo('grep "pre-up /opt/contrail/bin/if-vhost0" /etc/network/interfaces')
        if if_vhost0.failed:
            sudo('sed -i "/iface vhost0 inet static/a\    pre-up /opt/contrail/bin/if-vhost0" /etc/network/interfaces')
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
    if ostype in ['ubuntu']:
        old_kmod = '^kmod=.*'
        new_kmod = 'kmod=vrouter'
        insert_line_to_file(pattern=old_kmod, line=new_kmod, file_name=agent_param)

@task
@roles('build')
def upgrade_contrail(from_rel, pkg):
    """Upgrades all the contrail pkgs in all nodes."""
    execute('install_pkg_all', pkg)
    execute('zookeeper_rolling_restart')
    execute('stop_cfgm')
    execute('stop_rabbitmq')
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    execute('setup_rabbitmq_cluster', True)
    fixup_restart_haproxy_in_all_cfgm(1)
    execute('restart_cfgm')
    execute('upgrade_collector', from_rel, pkg)
    execute('upgrade_control', from_rel, pkg)
    execute('upgrade_webui', from_rel, pkg)
    execute('upgrade_vrouter', from_rel, pkg)
    execute('create_default_secgrp_rules')
    #execute('compute_reboot')
    execute('wait_till_all_up', waitdown='False', contrail_role='compute')
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
    execute('stop_cfgm')
    execute('stop_rabbitmq')
    execute('stop_collector')
    execute('upgrade_openstack', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_cfgm', from_rel, pkg)
    execute('setup_rabbitmq_cluster', True)
    fixup_restart_haproxy_in_all_cfgm(1)
    execute('restart_cfgm')
    execute('upgrade_collector', from_rel, pkg)
    execute('upgrade_control', from_rel, pkg)
    execute('upgrade_webui', from_rel, pkg)
    execute('upgrade_vrouter', from_rel, pkg)
    execute('create_default_secgrp_rules')
    #execute('compute_reboot')
    execute('wait_till_all_up', waitdown=False, contrail_role='compute')
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
            version = sudo("cat /opt/contrail/contrail_packages/VERSION | cut -d '=' -f2")
            version = version.strip()
            out = sudo("ls /opt/contrail/")
            if 'contrail_install_repo_%s' % version not in out:
                sudo("mv /opt/contrail/contrail_install_repo /opt/contrail/contrail_install_repo_%s" % version)

@task
@hosts(env.roledefs['cfgm'][0])
def check_and_setup_rabbitmq_cluster():
    if get_release() not in RELEASES_WITH_QPIDD:
        execute(setup_rabbitmq_cluster)

def fixup_device_manager_config(host_string):
    # contrail-device-manager.conf
    cfgm_ip = hstr_to_ip(host_string)
    rabbit_host = cfgm_ip
    rabbit_port = 5672
    internal_vip = get_contrail_internal_vip()
    if internal_vip:
        rabbit_host = internal_vip
        rabbit_port = 5673
    cassandra_host_list = [get_control_host_string(cassandra_host) for cassandra_host in env.roledefs['database']]
    cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in cassandra_host_list]
    cassandra_server_list = [(cassandra_server_ip, '9160') for cassandra_server_ip in cassandra_ip_list]
    zk_servers_ports = ','.join(['%s:2181' %(s) for s in cassandra_ip_list])
    template_vals = {'__rabbit_server_ip__': rabbit_host,
                     '__rabbit_server_port__': rabbit_port,
                     '__contrail_api_server_ip__': internal_vip or cfgm_ip,
                     '__contrail_api_server_port__': '8082',
                     '__contrail_zookeeper_server_ip__': zk_servers_ports,
                     '__contrail_log_file__' : '/var/log/contrail/contrail-device-manager.log',
                     '__contrail_cassandra_server_list__' : ' '.join('%s:%s' % cassandra_server for cassandra_server in cassandra_server_list),
                     '__contrail_disc_server_ip__': internal_vip or cfgm_ip,
                     '__contrail_disc_server_port__': '5998',
                    }
    tmp_fname_1 = 'contrail_device_manager_conf.py'
    tmp_fname_1_module = tmp_fname_1.strip('.py')
    tmp_fname_2 = 'contrail-device-manager.conf'
    with settings(host_string=host_string):
        if detect_ostype() == 'ubuntu':
            site_dir = run('python -c "import sysconfig; print sysconfig.get_path(\'platlib\')"')
        else:
            site_dir = run('python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"')
        get_as_sudo("%s/contrail_provisioning/config/templates/contrail_device_manager_conf.py" % site_dir, tmp_fname_1)
    sys.path.append(os.getcwd())
    tmp_fname_1_obj = __import__(tmp_fname_1_module)
    device_manager_conf = tmp_fname_1_obj.template.safe_substitute(template_vals)
    with open(tmp_fname_2, 'w') as cfg_file:
        cfg_file.write(device_manager_conf)
    with settings(host_string=host_string):
        put(tmp_fname_2, "/etc/contrail/contrail-device-manager.conf", use_sudo=True)
        sudo("chmod a+x /etc/init.d/contrail-device-manager")
    with settings(warn_only=True):
        sudo("rm -rf %s %s %sc" % (tmp_fname_1, tmp_fname_2, tmp_fname_1))

import os
from fabfile.config import *
from misc import zoolink
from fabfile.utils.fabos import (
       detect_ostype, get_openstack_services, get_openstack_sku,
       is_xenial_or_above)
from fabfile.utils.cluster import get_orchestrator
from fabric.contrib.files import exists
from fabfile.utils.host import hstr_to_ip, manage_config_db
from fabfile.utils.host import get_control_host_string

@task
@roles('cfgm')
def stop_rabbitmq():
    openstack_services = get_openstack_services()
    with settings(warn_only=True):
        sudo('service supervisor-support-service stop')
        sudo('service %s stop' % openstack_services['rabbitmq-server'])

@task
@roles('cfgm')
def restart_rabbitmq():
    openstack_services = get_openstack_services()
    sudo('service %s restart' % openstack_services['rabbitmq-server'])

@task
def stop_and_disable_qpidd():
    """stops the qpidd and disables it."""
    execute(stop_and_disable_qpidd_node, env.host_string)

@task
def stop_and_disable_qpidd_node(*args):
    """stops the qpidd and disables it in one node."""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if not sudo('service qpidd status').succeeded:
                print "qpidd not running, skipping stop."
                return
        with settings(host_string=host_string):
            sudo('service qpidd stop')
            sudo('chkconfig qpidd off')

@task
@roles('database')
def stop_database():
    """stops the contrail database services."""
    sudo('service contrail-database  stop')
    sudo('service supervisor-database  stop')

@task
@roles('cfgm')
def stop_cfgm():
    """stops the contrail config services."""
    execute('stop_cfgm_node', env.host_string)

@task
def stop_cfgm_node(*args):
    openstack_services = get_openstack_services()
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo('service supervisor-config stop')
            sudo('service neutron-server stop')
            sudo('service %s stop' % openstack_services['rabbitmq-server'])


@task
@roles('cfgm')
def stop_cfgm_db():
    """stops the contrail config db services."""
    execute('stop_cfgm_db_node', env.host_string)

@task
def stop_cfgm_db_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if manage_config_db():
                sudo('service contrail-database stop')
            sudo('service zookeeper stop')

@task
@roles('cfgm')
def start_cfgm():
    """starts the contrail config services."""
    execute('start_cfgm_node', env.host_string)

@task
def start_cfgm_node(*args):
    openstack_services = get_openstack_services()
    for host_string in args:
        with settings(host_string=host_string,warn_only=True):
            sudo('service %s start' % openstack_services['rabbitmq-server'])
            sudo('service supervisor-config start')
            sudo('service neutron-server start')


@task
@roles('cfgm')
def start_cfgm_db():
    """starts the contrail config db services."""
    execute('start_cfgm_node', env.host_string)

@task
def start_cfgm_db_node(*args):
    for host_string in args:
        with settings(host_string=host_string,warn_only=True):
            if manage_config_db():
                sudo('service contrail-database start')
            sudo('service zookeeper start')

@task
@roles('database')
def start_database():
    """Starts the contrail database services."""
    sudo('service contrail-database  start')
    sudo('service supervisor-database  start')

@task
@roles('control')
def start_control():
    """Starts the contrail control services."""
    sudo('service supervisor-control start')

@task
@roles('webui')
def start_webui():
    """starts the contrail webui services."""
    sudo('service supervisor-webui start')

@task
@roles('collector')
def start_collector():
    """starts the contrail collector services."""
    sudo('service supervisor-analytics start')

@task
@roles('control')
def stop_control():
    """Stops the contrail control services."""
    execute('stop_control_node', env.host_string)

@task
def stop_control_node(*args):
    """Stops the contrail control services in once control node. USAGE:fab stop_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string, warn_only=True):
            sudo('service supervisor-control stop')

@task
@roles('collector')
def stop_collector():
    """stops the contrail collector services."""
    execute('stop_collector_node', env.host_string)

@task
def stop_collector_node(*args):
    for host_string in args:
        with  settings(host_string=host_string, warn_only=True):
            if is_xenial_or_above():
                for svc in ['contrail-analytics-api',
                            'contrail-alarm-gen',
                            'contrail-analytics-nodemgr',
                            'contrail-collector',
                            'contrail-topology',
                            'contrail-snmp-collector']:
                    sudo('service %s stop' % svc)
            else:
                sudo('service supervisor-analytics stop')

@task
@roles('compute')
def stop_vrouter():
    """stops the contrail vrouter services."""
    sudo('service supervisor-vrouter stop')

@task
@roles('webui')
def stop_webui():
    """stops the contrail webui services."""
    execute('stop_webui_node', env.host_string)

@task
def stop_webui_node(*args):
    for host_string in args:
        with  settings(host_string=host_string, warn_only=True):
            sudo('service supervisor-webui stop')

@task
@roles('database')
def restart_database():
    """Restarts the contrail database services."""
    execute('restart_database_node', env.host_string)

@task
def restart_database_node(*args):
    """Restarts the contrail database services in once database node. USAGE:fab restart_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-database restart')

@task
@roles('openstack')
def restart_openstack():
    """Restarts the contrail openstack services."""
    execute('restart_openstack_node', env.host_string)

@task
def restart_openstack_node(*args):
    """Restarts the contrail openstack services in once openstack node. USAGE:fab restart_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    openstack_services = get_openstack_services()
    if detect_ostype() in ['ubuntu']:
        openstack_services['services'] += ['memcached']
    else:
        openstack_services['services'] += ['httpd', 'memcached']

    for host_string in args:
        with settings(host_string=host_string):
            for svc in openstack_services['services']:
                sudo('service %s restart' % svc)

@task
@roles('compute')
def restart_openstack_compute():
    """Restarts the contrail openstack compute service."""
    if 'tsn' in env.roledefs.keys() and env.host_string in env.roledefs['tsn']:
        return
    if get_orchestrator() == 'vcenter':
        return
    if detect_ostype() in ['ubuntu']:
        sudo('service nova-compute restart')
        return
    sudo('service openstack-nova-compute restart')

@task
@parallel
@roles('cfgm')
def restart_cfgm():
    """Restarts the contrail config services."""
    execute("restart_cfgm_node", env.host_string)

@task
def restart_cfgm_node(*args):
    """Restarts the contrail config services in once cfgm node. USAGE:fab restart_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    openstack_services = get_openstack_services()
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service %s restart' % openstack_services['rabbitmq-server'])
            sudo('service supervisor-config restart')
            if get_orchestrator() == 'openstack':
                sudo('service neutron-server restart')


@task
@parallel
@roles('cfgm')
def restart_cfgm_db():
    """Restarts the contrail config db services."""

@task
def restart_cfgm_db_node(*args):
    """Restarts the contrail config db services in once cfgm node. USAGE:fab restart_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            if manage_config_db():
                sudo('service contrail-database restart')
            sudo('service zookeeper restart')

@task
@roles('control')
def restart_control():
    """Restarts the contrail control services."""
    execute("restart_control_node", env.host_string)

@task
def restart_control_node(*args):
    """Restarts the contrail control services in once control node. USAGE:fab restart_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-control restart')

@task
@roles('collector')
def restart_collector():
    """Restarts the contrail collector services."""
    execute('restart_collector_node', env.host_string)

@task
def restart_collector_node(*args):
    """Restarts the contrail collector services in once collector node. USAGE:fab restart_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-analytics restart')

@task
@roles('compute')
def restart_vrouter():
    """Restarts the contrail compute services."""
    execute('restart_vrouter_node', env.host_string)

@task
def restart_vrouter_node(*args):
    """Restarts the contrail vrouter services in once vrouter node. USAGE:fab restart_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-vrouter restart')

@task
@roles('webui')
def restart_webui():
    """Restarts the contrail webui services."""
    execute('restart_webui_node', env.host_string)

@task
def restart_webui_node(*args):
    """Restarts the contrail webui services in once webui node. USAGE:fab restart_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-webui restart')

@task
@roles('webui')
def start_redis_webui():
    """Starts redis service in webui node."""
    execute('start_redis_webui_node', env.host_string)

@task
def start_redis_webui_node(*args):
    """Starts redis service in webui node. USAGE:fab start_redis_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            run('chkconfig redis on')
            run('service redis start')

@task
@roles('build')
def stop_contrail_control_services():
    """stops the Contrail config,control,analytics,database,webui services."""
    execute('stop_cfgm')
    execute('stop_database')
    execute('stop_collector')
    execute('stop_control')
    execute('stop_webui')

@task
@roles('build')
def start_contrail_control_services():
    """Starts the Contrail config,control,analytics,database,webui services."""
    execute('start_cfgm')
    execute('start_database')
    execute('start_collector')
    execute('start_control')
    execute('start_webui')

@task
@roles('cfgm')
def backup_cassandra_zk():
    """take backup of cassandra db"""
    data_dir = None
    out = ''
    cmd = "sed -n '/data_file_directories/{n;p;}'"
    # If Ubuntu
    if exists('/etc/cassandra/cassandra.yaml', use_sudo=True):
        yaml_file = '/etc/cassandra/cassandra.yaml'
        out = sudo("%s %s" % (cmd, yaml_file))
    # If redhat distros
    elif exists('/etc/cassandra/conf/cassandra.yaml', use_sudo=True):
        yaml_file = '/etc/cassandra/conf/cassandra.yaml'
        out = sudo("%s %s" % (cmd, yaml_file))
    data_dir = out[2:]
    if data_dir is None:
        cassandra_dir = '/var/lib/cassandra'
    else:
        cassandra_dir = os.path.abspath(os.path.join(data_dir,os.pardir))
    if exists(cassandra_dir+'.old'):
        sudo('rm -rf '+cassandra_dir+'.old')
    if exists(cassandra_dir):
        sudo('mv '+ cassandra_dir+' '+ cassandra_dir+'.old')
    if exists('/var/lib/zookeeper/version-2.old'):
        sudo('rm -rf /var/lib/zookeeper/version-2.old')
    if exists('/var/lib/zookeeper/version-2'):
        sudo('mv /var/lib/zookeeper/version-2 /var/lib/zookeeper/version-2.old')

@task
@roles('build')
def restart_contrail_control_services():
    """Restarts the Contrail config,control,analytics,database,webui services."""
    execute('restart_cfgm') 
    execute('restart_database')
    execute('restart_collector')
    execute('restart_control')
    execute('restart_webui')

@roles('openstack')
def stop_nova():
    """Stop nova services :fab stop_nova"""
    host = env.host_string
    openstack_services = ['nova-api', 'nova-scheduler',
                          'nova-conductor']
    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s stop' % svc)


@roles('openstack')
def start_nova():
    """Start nova services :fab stop_nova"""
    host = env.host_string
    openstack_services = ['nova-api', 'nova-scheduler',
                          'nova-conductor']
    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s start' % svc)


@roles('openstack')
def stop_keystone():
    """Stop keystone  services :fab stop_keystone"""
    host = env.host_string
    openstack_services = ['keystone']

    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s stop' % svc)

@roles('openstack')
def start_keystone():
    """Start keystone  services :fab start_keystone"""
    host = env.host_string
    openstack_services = ['keystone']

    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s start' % svc)



@roles('openstack')
def stop_glance():
    """Stop keystone  services :fab stop_keystone"""
    host = env.host_string
    openstack_services = ['glance-api','glance-registry']

    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s stop' % svc)

@roles('openstack')
def start_glance():
    """Start keystone  services :fab start_keystone"""
    host = env.host_string
    openstack_services = ['glance-api','glance-registry']

    with settings(host_string=host):
        for svc in openstack_services:
            sudo('service %s start' % svc)


@roles('compute')
def stop_nova_openstack_compute():
    """Stop the contrail openstack compute service."""
    tsn_nodes = []
    tor_nodes = []
    host = env.host_string
    if 'tsn' in env.roledefs:
        tsn_nodes = env.roledefs['tsn']
    if 'toragent' in env.roledefs:
        tor_nodes = env.roledefs['toragent']
    if host not in (tsn_nodes and tor_nodes) :
        if detect_ostype() in ['ubuntu']:
            sudo('service nova-compute stop')
            return
        sudo('service openstack-nova-compute stop')


@roles('compute')
def start_nova_openstack_compute():
    """Start the contrail openstack compute service."""
    tsn_nodes = []
    tor_nodes = []
    host = env.host_string
    if 'tsn' in env.roledefs:
        tsn_nodes = env.roledefs['tsn']
    if 'toragent' in env.roledefs:
        tor_nodes = env.roledefs['toragent']
    if host not in (tsn_nodes and tor_nodes) :
        if detect_ostype() in ['ubuntu']:
            sudo('service nova-compute start')
            return
        sudo('service openstack-nova-compute start')


@roles('openstack')
def reboot_nova_instance():
    host = env.host_string
    with settings(host_string=host,warn_only=True):
        sudo(
            "source /etc/contrail/openstackrc;nova  list --all_tenants  | awk '{print $2}' | grep -v ID | xargs -L1 nova reboot --hard $2")

@task
def drop_analytics_keyspace_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            CASSANDRA_CMD = 'cqlsh %s -f ' % hstr_to_ip(get_control_host_string(host_string))
            print "Dropping analytics keyspace.. this may take a while.."
            sudo("echo 'describe keyspace \"ContrailAnalytics\";' > /tmp/cassandra_commands_file")
            if sudo(CASSANDRA_CMD + '/tmp/cassandra_commands_file').succeeded:
                sudo("echo 'drop keyspace \"ContrailAnalytics\";' > /tmp/cassandra_commands_file")
                if not sudo(CASSANDRA_CMD + '/tmp/cassandra_commands_file').succeeded:
                    print "WARN: Drop keyspace ContrailAnalytics failed.."
                else:
                    print "INFO: keyspace ContrailAnalytics is dropped.."
                    print "INFO: if snapshots are created, manual deletion may be required to free up disk.."
            sudo("echo 'drop keyspace \"ContrailAnalyticsCql\";' > /tmp/cassandra_commands_file")
            if not sudo(CASSANDRA_CMD + '/tmp/cassandra_commands_file').succeeded:
                print "WARN: Drop keyspace ContrailAnalyticsCql failed.."
            else:
                print "INFO: keyspace ContrailAnalyticsCql is dropped.."
                print "INFO: if snapshots are created, manual deletion may be required to free up disk.."

@task
@roles('build')
def drop_analytics_keyspace(confirm=False):
    if not confirm:
        print "WARN: Dropping analytics keyspace will cause analytics data to be lost permanently..."
        if raw_input("Continue? Yes/No: ") != "Yes":
            print "INFO: Not confirmed. Exiting..."
            return

    execute('stop_collector')
    execute("drop_analytics_keyspace_node", env.roledefs['database'][0])

@task
@roles('openstack')
def restart_openstack_on_demand():
    ''' Restart openstack services for
        https://bugs.launchpad.net/juniperopenstack/+bug/1610024
    '''
    if detect_ostype() in ['centoslinux'] and get_openstack_sku() in ['kilo']:
        execute('restart_openstack_node', env.host_string)

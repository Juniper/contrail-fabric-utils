from fabfile.config import *
from misc import zoolink
from fabfile.utils.fabos import detect_ostype

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
    #sudo('service supervisord-contrail-database  stop')
    sudo('service supervisor-database  stop')

@task
@roles('cfgm')
def stop_cfgm():
    """stops the contrail config services."""
    execute('stop_cfgm_node', env.host_string)

@task
def stop_cfgm_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo('service supervisor-config stop')
            sudo('service neutron-server stop')
            sudo('service supervisor-support-service stop')

@task
@roles('cfgm')
def start_cfgm():
    """starts the contrail config services."""
    with settings(warn_only=True):
        sudo('service supervisor-support-service start')
        sudo('service supervisor-config start')
        sudo('service neutron-server start')

@task
@roles('database')
def start_database():
    """Starts the contrail database services."""
    #sudo('service supervisord-contrail-database  start')
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
        with  settings(host_string=host_string):
            sudo('service supervisor-control stop')

@task
@roles('collector')
def stop_collector():
    """stops the contrail collector services."""
    with settings(warn_only=True):
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
            execute('zoolink_node', host_string)
            zoo_svc = 'zookeeper'
            sudo('service %s restart' % zoo_svc)

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
    openstack_services = [ 'httpd', 'memcached', 'supervisor-openstack']
    if detect_ostype() in ['ubuntu']:
        openstack_services = ['memcached', 'supervisor-openstack']

    for host_string in args:
        with  settings(host_string=host_string):
            for svc in openstack_services:
                sudo('service %s restart' % svc)

@task
@roles('compute')
def restart_openstack_compute():
    """Restarts the contrail openstack compute service."""
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
    for host_string in args:
        with  settings(host_string=host_string):
            sudo('service supervisor-support-service restart')
            sudo('service supervisor-config restart')
            sudo('service neutron-server restart')

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
    if detect_ostype() in ['ubuntu']:
        sudo('service nova-compute stop')
        return
    sudo('service openstack-nova-compute stop')


@roles('compute')
def start_nova_openstack_compute():
    """Start the contrail openstack compute service."""
    if detect_ostype() in ['ubuntu']:
        sudo('service nova-compute start')
        return
    sudo('service openstack-nova-compute start')


@roles('openstack')
def reboot_nova_instance():
    host = env.host_string
    with settings(host_string=host,warn_only=True):
        sudo(
            "source /etc/contrail/openstackrc;nova  list --all_tenants  | awk '{print $2}' | xargs -L1 nova reboot --hard $2")



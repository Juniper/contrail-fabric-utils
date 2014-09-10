from time import sleep

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype

class OpenStackSetupError(Exception):
    pass

def verify_service(service):
    for x in xrange(10):
        output = run("service %s status" % service)
        if 'running' in output.lower():
            return
        else:
            sleep(20)
    raise SystemExit("Service %s not running." % service)
    
@task
@roles('database')
def verify_database():
    zoo_svc = 'zookeeper'
    verify_service(zoo_svc)
    verify_service("supervisor-database")
    verify_service("contrail-database")

@task
@roles('webui')
def verify_webui():
    verify_service("supervisor-webui")
    #verify_service("contrail-webui-middleware")

@task
@roles('openstack')
def verify_openstack():
    if detect_ostype() in ['Ubuntu']:
        verify_service("keystone")
    else:
        verify_service("openstack-keystone")
    output = run("source /etc/contrail/openstackrc; keystone tenant-list")
    if 'error' in output:
        raise OpenStackSetupError(output)

@task
@roles('cfgm')
def verify_cfgm():
    verify_service("supervisor-config")
    verify_service("contrail-api")
    verify_service("contrail-discovery")
    verify_service("contrail-schema")
    verify_service("contrail-svc-monitor")

@task
@roles('control')
def verify_control():
    verify_service("supervisor-control")
    verify_service("contrail-control")
    #verify_service("supervisor-dns")
    #verify_service("contrail-dns")
    #verify_service("contrail-named")

@task
@roles('collector')
def verify_collector():
    verify_service("supervisor-analytics")
    verify_service("contrail-collector")
    verify_service("contrail-analytics-api")
    verify_service("contrail-query-engine")

@task
@roles('compute')
def verify_compute():
    verify_service("supervisor-vrouter")
    #verify_service("contrail-vrouter")


@task
@roles('compute')
def remove_startup_files():
    compute = env.host_string
    if compute not in env.roledefs['database']:
        run("rm /etc/init/supervisord-contrail-database.conf")
        run("rm /etc/contrail/supervisord_contrail_database.conf")
    if compute not in env.roledefs['collector']:
        run("rm /etc/init/supervisor-analytics.conf")
        run("rm /etc/contrail/supervisord_analytics.conf")
    if compute not in env.roledefs['webui']:
        run("rm /etc/init/supervisor-webui.conf")
        run("rm /etc/contrail/supervisord_webui.conf")
    if compute not in env.roledefs['cfgm']:
        run("rm /etc/init/supervisor-config.conf")
        run("rm /etc/contrail/supervisord_config.conf")
    if compute not in env.roledefs['control']:
        run("rm /etc/init/supervisor-dns.conf")
        run("rm /etc/init/supervisor-control.conf") 
        run("rm /etc/contrail/supervisord_dns.conf")
        run("rm /etc/contrail/supervisord_control.conf")
    if compute not in env.roledefs['compute']:
        run("rm /etc/init/supervisor-vrouter.conf")
        run("rm /etc/contrail/supervisord_vrouter.conf")

@task
@roles('compute')
def stop_glance_in_compute():
    compute = env.host_string
    if compute not in env.roledefs['cfgm']:
       run("service glance-api stop")
       run("service glance-registry stop")

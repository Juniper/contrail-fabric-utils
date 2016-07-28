from time import sleep

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_openstack_services
from fabfile.utils.cluster import get_orchestrator
from fabfile.utils.host import (keystone_ssl_enabled,
        get_keystone_insecure_flag)
import re

class OpenStackSetupError(Exception):
    pass

def verify_service(service, initd_service=False):
    for x in xrange(10):
        with settings(warn_only=True):
            output = sudo("service %s status" % service)
        if initd_service:
            if output.succeeded or re.search('Active:.*active', output):
                return
            else:
                sleep(20)
        else:
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
    verify_service("contrail-database", initd_service=True)

@task
@roles('webui')
def verify_webui():
    verify_service("supervisor-webui")
    #verify_service("contrail-webui-middleware")

@task
@roles('openstack')
def verify_openstack():
    openstack_services = get_openstack_services()
    verify_service(openstack_services["keystone"])
    insecure_flag = ''
    if keystone_ssl_enabled() and get_keystone_insecure_flag():
        insecure_flag = '--insecure'
    for x in xrange(10):
        with settings(warn_only=True):
            output = sudo("source /etc/contrail/openstackrc; keystone %s tenant-list" % insecure_flag)
        if output.failed:
            sleep(10)
        else:
            return
    raise OpenStackSetupError(output)

@task
@roles('cfgm')
def verify_cfgm():
    verify_service("supervisor-config")
    verify_service("contrail-api")
    verify_service("contrail-discovery")
    verify_service("contrail-schema")
    if get_orchestrator is 'openstack':
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
        sudo("rm /etc/init/supervisord-contrail-database.conf")
        sudo("rm /etc/contrail/supervisord_contrail_database.conf")
    if compute not in env.roledefs['collector']:
        sudo("rm /etc/init/supervisor-analytics.conf")
        sudo("rm /etc/contrail/supervisord_analytics.conf")
    if compute not in env.roledefs['webui']:
        sudo("rm /etc/init/supervisor-webui.conf")
        sudo("rm /etc/contrail/supervisord_webui.conf")
    if compute not in env.roledefs['cfgm']:
        sudo("rm /etc/init/supervisor-config.conf")
        sudo("rm /etc/contrail/supervisord_config.conf")
    if compute not in env.roledefs['control']:
        sudo("rm /etc/init/supervisor-dns.conf")
        sudo("rm /etc/init/supervisor-control.conf") 
        sudo("rm /etc/contrail/supervisord_dns.conf")
        sudo("rm /etc/contrail/supervisord_control.conf")
    if compute not in env.roledefs['compute']:
        sudo("rm /etc/init/supervisor-vrouter.conf")
        sudo("rm /etc/contrail/supervisord_vrouter.conf")

@task
@roles('compute')
def stop_glance_in_compute():
    compute = env.host_string
    if compute not in env.roledefs['cfgm']:
       sudo("service glance-api stop")
       sudo("service glance-registry stop")

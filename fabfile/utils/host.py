import paramiko
from netaddr import *
from copy import deepcopy

from fabric.api import env, sudo, get, put, run
from fabric.context_managers import settings

from fabfile.config import testbed
from fabfile.utils.cluster import get_orchestrator

def hstr_to_ip(host_string):
    return host_string.split('@')[1]

def hstr_to_user(host_string):
    return host_string.split('@')[0]

def get_control_host_string(mgmt_host):
    ctrl_ip_info= getattr(testbed, 'control_data', None)
    host_details= mgmt_host
    if ctrl_ip_info:
        if mgmt_host in ctrl_ip_info.keys():
            ip = str(IPNetwork(ctrl_ip_info[mgmt_host]['ip']).ip)
            user= mgmt_host.split('@')[0]
            host_details= user+'@'+ip
    return host_details

def get_manage_neutron():
    return get_from_testbed_dict('keystone','manage_neutron', 'yes')

def get_provision_neutron_server():
    return get_from_testbed_dict('cfgm','provision_neutron_server', 'yes')

def get_neutron_password():
    admin_passwd = get_authserver_admin_password()
    return get_from_testbed_dict('keystone','neutron_password', admin_passwd)

def get_nova_password():
    admin_passwd = get_authserver_admin_password()
    return get_from_testbed_dict('keystone','nova_password', admin_passwd)

def get_service_token():
    if get_orchestrator() is not 'openstack':
        with settings(host_string=env.roledefs['cfgm'][0], warn_only=True):
            if sudo("sudo ls /etc/contrail/service.token").failed:
                sudo("sudo setup-service-token.sh")
            service_token = sudo("sudo cat /etc/contrail/service.token")
        return service_token

    service_token = get_from_testbed_dict('openstack','service_token',
                             getattr(testbed, 'service_token', ''))
    if not service_token:
        with settings(host_string=env.roledefs['openstack'][0], warn_only=True):
            if sudo("sudo ls /etc/contrail/service.token").failed:
                sudo("sudo setup-service-token.sh")
            service_token = sudo("sudo cat /etc/contrail/service.token")
    return service_token


def get_haproxy_token(role='cfgm'):
    haproxy_token = get_from_testbed_dict(role, 'haproxy_token', None)
    if not haproxy_token:
        hap_token_file = "/etc/contrail/haproxy.token"
        with settings(host_string=env.roledefs[role][0], warn_only=True):
            if sudo("sudo ls %s" % hap_token_file).failed:
                sudo("mkdir -p /etc/contrail/")
                sudo("openssl rand -hex 10 > %s" % hap_token_file)
                sudo("chmod 400 %s" % hap_token_file)
            haproxy_token = sudo("cat %s" % hap_token_file)
    return haproxy_token


def get_service_dbpass():
    return get_from_testbed_dict('openstack','service_dbpass', 'c0ntrail123')


def copy_openstackrc(role='compute'):
    openstackrc = "/etc/contrail/openstackrc"
    temprc = "/tmp/openstackrc"
    with settings(host_string=env.roledefs['openstack'][0]):
        get(openstackrc, temprc)
    for host_string in env.roledefs[role]:
        with settings(host_string=host_string):
            put(temprc, openstackrc, use_sudo=True)

def get_service_token_opt():
    service_token = get_service_token()
    if service_token:
        return '--service_token %s' % (service_token)
    else:
        return ''

def get_haproxy():
    if get_contrail_internal_vip():
        # Do not pass haproxy option to the provisioning scripts in HA setup,
        # As the setup_ha task takes care of configuring VIP and VIP will be
        # used instead of 127.0.0.1.
        return False
    return getattr(testbed, 'haproxy', False)

def get_sriov_enabled():
    if 'sriov' not in env.keys():
        return False

    for compute in env.roledefs['compute']:
        if compute in env.sriov:
            return True

    return False

def get_haproxy_opt():
    haproxy_opt = '--haproxy' if get_haproxy() else ''
    return haproxy_opt

def get_region_name():
    region_name = getattr(testbed, 'region_name', 'RegionOne')
    return get_from_testbed_dict('keystone', 'region_name', region_name)

def get_region_name_opt():
    region_name = get_region_name()
    return '--region_name %s' %(region_name)


def get_vcenter_ip():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k,'server', None)

def get_vcenter_port():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k,'port', None)

def get_vcenter_username():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k, 'username', None)

def get_vcenter_password():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k, 'password', None)

def get_vcenter_datacenter():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k, 'datacenter', None)

def get_vcenter_compute():
    if env.has_key('vcenter_servers'):
        for k in env.vcenter_servers.keys():
            return get_from_vcenter_dict(k, 'vcenter_compute', None)

def get_authserver_ip(ignore_vip=False, openstack_node=None):
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       for k in env.vcenter_servers.keys():
           return get_from_vcenter_dict(k, 'server', None)
    # openstack
    if openstack_node:
        openstack_host = get_control_host_string(openstack_node)
    else:
        if 'openstack' in testbed.env.roledefs and len(testbed.env.roledefs['openstack']) > 0:
            openstack_host = get_control_host_string(testbed.env.roledefs['openstack'][0])
            openstack_ip = hstr_to_ip(openstack_host)
    openstack_ip = hstr_to_ip(openstack_host)
    keystone_ip1 = getattr(testbed, 'keystone_ip', None)
    keystone_ip = get_from_testbed_dict('keystone', 'keystone_ip', keystone_ip1)
    internal_vip = get_openstack_internal_vip()

    if ignore_vip:
        return keystone_ip or openstack_ip
    else:
        if internal_vip and keystone_ip:
            print "Openstack HA setup, Keystone running in different node other than [%s]" % ','.join(testbed.env.roledefs['openstack'])
            return keystone_ip
        elif keystone_ip:
            print "Keystone running in different node other than [%s]" % ','.join(testbed.env.roledefs['openstack'])
            return keystone_ip
        elif internal_vip:
            print "Openstack HA setup, Keystone running in nodes [%s]" % ','.join(testbed.env.roledefs['openstack'])
            return internal_vip
        return openstack_ip

def get_from_vcenter_dict(dictionary, key, default_value):
    
    try:
        val = env['vcenter_servers'][dictionary][key]
    except KeyError:
        val = default_value
    return val


def get_from_testbed_dict( dictionary, key,default_value):
    try:
        val = env[dictionary][key]
    except KeyError:
        val = default_value
    return val

def get_authserver_protocol():
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       for k in env.vcenter_servers.keys():
           return get_from_vcenter_dict(k, 'auth', 'https')
    # openstack
    auth_protocol = 'http'
    return get_from_testbed_dict('keystone', 'auth_protocol', auth_protocol)

def get_apiserver_protocol():
    return get_from_testbed_dict('cfgm', 'auth_protocol', 'http')

def get_keystone_version():
    return get_from_testbed_dict('keystone', 'version', 'v2.0')

def get_keystone_version():
    return get_from_testbed_dict('keystone', 'version', 'v2.0')

def get_keystone_insecure_flag():
    return get_from_testbed_dict('keystone', 'insecure', 'False')

def get_authserver_port():
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       for k in env.vcenter_servers.keys():
           return get_from_vcenter_dict(k, 'port', 443)
    # openstack
    return get_from_testbed_dict('keystone', 'auth_port','35357')

def get_keystone_admin_token():
    token = get_from_testbed_dict('keystone', 'admin_token', None)
    if token:
        return token
    keystone_ip = get_authserver_ip(ignore_vip=True)
    openstack_node = testbed.env.roledefs['openstack'][0]
    if keystone_ip == hstr_to_ip(get_control_host_string(openstack_node)):
        # Use Management interface IP to ssh
        keystone_ip = hstr_to_ip(openstack_node)
    cmd = 'grep "^[ ]*admin_token" /etc/keystone/keystone.conf | tr -d \' \'| awk -F"=" {\'print $2\'}'
    with settings(host_string='%s@%s' % (hstr_to_user(openstack_node), keystone_ip)):
        token = sudo(cmd)
    return token

def get_authserver_admin_user():
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       for k in env.vcenter_servers.keys():
           return env.vcenter_servers[k]['username']
    # openstack
    ks_admin_user = getattr(testbed, 'keystone_admin_user','admin')
    return get_from_testbed_dict('keystone', 'admin_user', ks_admin_user) 

def get_authserver_admin_password():
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       for k in env.vcenter_servers.keys():
           return env.vcenter_servers[k]['password']
    # openstack
    os_admin_password = getattr(env,'openstack_admin_password', 'contrail123')
    ks_admin_password = getattr(testbed, 
                          'keystone_admin_password', os_admin_password)
    return get_from_testbed_dict('keystone', 
            'admin_password', ks_admin_password) 

def get_authserver_credentials():
    return get_authserver_admin_user(), get_authserver_admin_password()

def get_keystone_service_tenant_name():
    return get_from_testbed_dict('keystone', 'service_tenant', 'service')

def get_admin_tenant_name():
    orch = getattr(env, 'orchestrator', 'openstack')
    if orch == 'vcenter':
       return 'vCenter'
    admin_tenant_name = getattr(testbed, 'os_tenant_name', 'admin')
    return get_from_testbed_dict('keystone', 'admin_tenant', 'admin')

def get_openstack_internal_vip():
    return get_from_testbed_dict('ha', 'internal_vip', None)

def get_openstack_external_vip():
    return get_from_testbed_dict('ha', 'external_vip', None)

def get_openstack_internal_virtual_router_id():
    return get_from_testbed_dict('ha', 'internal_virtual_router_id', 100)

def get_openstack_external_virtual_router_id():
    return get_from_testbed_dict('ha', 'external_virtual_router_id', get_openstack_internal_virtual_router_id())

def get_provision_openstack_ha():
    return get_from_testbed_dict('ha', 'provision_openstack_ha', None)

def get_contrail_internal_vip():
    vip = get_from_testbed_dict('ha', 'internal_vip', None)
    return get_from_testbed_dict('ha', 'contrail_internal_vip', vip)

def get_contrail_external_vip():
    vip = get_from_testbed_dict('ha', 'external_vip', None)
    return get_from_testbed_dict('ha', 'contrail_external_vip', vip)

def get_contrail_internal_virtual_router_id():
    return get_from_testbed_dict('ha', 'contrail_internal_virtual_router_id', get_openstack_internal_virtual_router_id())

def get_contrail_external_virtual_router_id():
    return get_from_testbed_dict('ha', 'contrail_external_virtual_router_id', get_contrail_internal_virtual_router_id())

def get_openstack_amqp_server():
    amqp_in_role = 'cfgm'
    rabbit_vip = get_contrail_internal_vip()
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        amqp_in_role = 'openstack'
        rabbit_vip = get_openstack_internal_vip()
    return get_from_testbed_dict('openstack','amqp_host',
        (rabbit_vip or hstr_to_ip(get_control_host_string(env.roledefs[amqp_in_role][0]))))

def get_openstack_amqp_port():
    rabbit_port = 5672
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        if get_openstack_internal_vip():
            rabbit_port = 5673
    else:
        if get_contrail_internal_vip():
            rabbit_port = 5673
    return get_from_testbed_dict('openstack','amqp_port', rabbit_port)

def get_contrail_amqp_server():
    """Returns first cfgm ip in case of non HA setup and
       contrail_internal_vip in case of HA setup
    """
    internal_vip = get_contrail_internal_vip()
    return (internal_vip or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0])))

def get_amqp_servers():
    """Returns a list of amqp servers"""
    amqp_ip_list = get_from_testbed_dict('cfgm', 'amqp_hosts',
                       [hstr_to_ip(get_control_host_string(amqp_host))
                        for amqp_host in env.roledefs['cfgm']])
    return amqp_ip_list

def get_amqp_password():
    """Returns amqp - rabbitmq password"""
    return get_from_testbed_dict('cfgm', 'amqp_password', '')

def get_amqp_port():
    return get_from_testbed_dict('cfgm', 'amqp_port', '5672')

def get_quantum_service_protocol():
    auth_proto = 'http'
    if apiserver_ssl_enabled():
        auth_proto = 'https'
    return get_from_testbed_dict('neutron', 'protocol', auth_proto)
    
def verify_sshd(host, user, password):

    import socket
    port = 22
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        s.connect((host, int(port)))
        s.shutdown(2)
        # Now check if paramiko connect passes
        # This is needed since during reimage, connect to port 22 
        # may still work, but it would still be in the process of reimage
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if password:
                client.connect(host, username=user, password=password, timeout=5)
            else:
                client.connect(host, username=user, key_filename=env.key_filename, timeout=5)
        except Exception,e:
            return False
        return True
    except socket.error as e:
        return False
    s.close()

def get_nova_cpu_mode():
    return get_from_testbed_dict('nova', 'cpu_mode', None)

def get_nova_cpu_model():
    return get_from_testbed_dict('nova', 'cpu_model', None)

def get_hypervisor(host_string):
    return get_from_testbed_dict('hypervisor', host_string, 'libvirt')

def get_env_passwords(host_string):
    return get_from_testbed_dict('passwords', host_string, None)

def get_nova_workers():
    osapi_compute_workers = get_from_testbed_dict('openstack', 'osapi_compute_workers', 40)
    conductor_workers = get_from_testbed_dict('openstack', 'conductor_workers', 40)
    return (osapi_compute_workers, conductor_workers)

def is_tor_agent_index_range_valid(range_str, host_string):
    toragent_dict = getattr(env,'tor_agent', None)
    if not host_string in toragent_dict:
        print 'tor-agent entry for %s does not exist in testbed file' \
            %(host_string)
        return False
    if not "-" in range_str:
        print "Invalid range %s" %(range_str)
        return False
    if range_str.startswith("-") or range_str.endswith("-"):
        print "Invalid range %s" %(range_str)
        return False
    range_array = range_str.split('-')
    if len(range_array) != 2 or int(range_array[0]) > int(range_array[1]):
        print "Invalid range %s" %(range_str)
        return False
    if not int(range_array[1]) < len(toragent_dict[host_string]):
        print "Index %d is more than the max permitted index in testbed file" \
            % int(range_array[1])
        return False
    return True
#end is_tor_agent_index_range_valid

def get_bgp_md5(host = env.host_string):
    """ Gets md5 data if present
        1. If md5 is supplied in testbed, retrieve its value from testbed
        2. if not defined in testbed, return none
    """
    return get_from_testbed_dict('md5', host, None)
#end get_bgp_md5


def manage_config_db():
    cfgm_nodes = set(deepcopy(env.roledefs['cfgm']))
    database_nodes = set(deepcopy(env.roledefs['database']))
    if (get_from_testbed_dict('cfgm', 'manage_db', 'yes') == 'yes' and
            database_nodes != cfgm_nodes and
            not cfgm_nodes.issubset(database_nodes)):
        return True
    return False


def get_keystone_certfile():
    default = '/etc/keystone/ssl/certs/keystone.pem'
    return get_from_testbed_dict('keystone','certfile', default)


def get_keystone_keyfile():
    default = '/etc/keystone/ssl/private/keystone.key'
    return get_from_testbed_dict('keystone','keyfile', default)


def get_keystone_cafile():
    default = '/etc/keystone/ssl/certs/keystone_ca.pem'
    return get_from_testbed_dict('keystone','cafile', default)


def get_keystone_cert_bundle():
    return '/etc/keystone/ssl/certs/keystonecertbundle.pem'


def get_apiserver_certfile():
    default = '/etc/contrail/ssl/certs/contrail.pem'
    return get_from_testbed_dict('cfgm','certfile', default)


def get_apiserver_keyfile():
    default = '/etc/contrail/ssl/private/contrail.key'
    return get_from_testbed_dict('cfgm','keyfile', default)


def get_apiserver_cafile():
    default = '/etc/contrail/ssl/certs/contrail_ca.pem'
    return get_from_testbed_dict('cfgm','cafile', default)


def get_apiserver_cert_bundle():
    return '/etc/contrail/ssl/certs/contrailcertbundle.pem'


def keystone_ssl_enabled():
    ssl = False
    auth_protocol = get_from_testbed_dict('keystone', 'auth_protocol', 'http')
    if auth_protocol == 'https':
        ssl = True
    return ssl



def apiserver_ssl_enabled():
    ssl = False
    auth_protocol = get_apiserver_protocol()
    if auth_protocol == 'https':
        ssl = True
    return ssl



def get_apiserver_insecure_flag():
    return get_from_testbed_dict('cfgm', 'insecure', 'False')


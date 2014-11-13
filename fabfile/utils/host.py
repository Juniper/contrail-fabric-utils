import paramiko
from netaddr import *

from fabric.api import env, sudo
from fabric.context_managers import settings

from fabfile.config import testbed
from fabfile.utils.cluster import get_orchestrator

def hstr_to_ip(host_string):
    return host_string.split('@')[1]

def hstr_to_user(host_string):
    return host_string.split('@')[0]

def get_control_host_string(mgmt_host):
    ctrl_ip_info= getattr(testbed, 'control_data', None)
    if ctrl_ip_info:
        if mgmt_host in ctrl_ip_info.keys():
            ip = str(IPNetwork(ctrl_ip_info[mgmt_host]['ip']).ip)
            user= mgmt_host.split('@')[0]
            host_details= user+'@'+ip
    else :
        host_details= mgmt_host
    return host_details

def get_manage_neutron():
    return get_from_testbed_dict('keystone','manage_neutron', 'yes')

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

def get_haproxy_opt():
    haproxy_opt = '--haproxy' if get_haproxy() else ''
    return haproxy_opt

def get_region_name():
    region_name = getattr(testbed, 'region_name', 'RegionOne')
    return get_from_testbed_dict('keystone', 'region_name', region_name)

def get_region_name_opt():
    region_name = get_region_name()
    return '--region_name %s' %(region_name)


def get_keystone_ip(ignore_vip=False, openstack_node=None):
    if openstack_node:
        openstack_host = get_control_host_string(openstack_node)
    else:
        openstack_host = get_control_host_string(testbed.env.roledefs['openstack'][0])
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

def get_keystone_ip_opt():
    keystone_ip = get_keystone_ip()
    return '--keystone_ip %s' % (keystone_ip)

def get_from_testbed_dict( dictionary, key,default_value):
    try:
        val = env[dictionary][key]
    except KeyError:
        val = default_value
    return val

def get_keystone_auth_protocol():
    return get_from_testbed_dict('keystone', 'auth_protocol','http')

def get_keystone_insecure_flag():
    return get_from_testbed_dict('keystone', 'insecure', 'False')

def get_keystone_auth_port():
    return get_from_testbed_dict('keystone', 'auth_port','35357')

def get_keystone_admin_token():
    token = get_from_testbed_dict('keystone', 'admin_token', None)
    if token:
        return token
    keystone_ip = get_keystone_ip(ignore_vip=True)
    openstack_node = testbed.env.roledefs['openstack'][0]
    if keystone_ip == hstr_to_ip(get_control_host_string(openstack_node)):
        # Use Management interface IP to ssh
        keystone_ip = hstr_to_ip(openstack_node)
    cmd = 'grep "^[ ]*admin_token" /etc/keystone/keystone.conf | tr -d \' \'| awk -F"=" {\'print $2\'}'
    with settings(host_string='%s@%s' % (hstr_to_user(openstack_node), keystone_ip)):
        token = sudo(cmd)
    return token

def get_keystone_admin_user():
    ks_admin_user = getattr(testbed, 'keystone_admin_user','admin')
    return get_from_testbed_dict('keystone', 'admin_user', ks_admin_user) 

def get_keystone_admin_password():
    os_admin_password = getattr(env,'openstack_admin_password', 'contrail123')
    ks_admin_password = getattr(testbed, 
                          'keystone_admin_password', os_admin_password)
    return get_from_testbed_dict('keystone', 
            'admin_password', ks_admin_password) 

def get_keystone_service_tenant_name():
    return get_from_testbed_dict('keystone', 'service_tenant', 'service')

def get_keystone_admin_tenant_name():
    admin_tenant_name = getattr(testbed, 'os_tenant_name', 'admin')
    return get_from_testbed_dict('keystone', 'admin_tenant', 'admin')

def get_openstack_internal_vip():
    return get_from_testbed_dict('ha', 'internal_vip', None)

def get_openstack_external_vip():
    return get_from_testbed_dict('ha', 'external_vip', None)

def get_contrail_internal_vip():
    vip = get_from_testbed_dict('ha', 'internal_vip', None)
    return get_from_testbed_dict('ha', 'contrail_internal_vip', vip)

def get_contrail_external_vip():
    vip = get_from_testbed_dict('ha', 'external_vip', None)
    return get_from_testbed_dict('ha', 'contrail_external_vip', vip)

def get_openstack_amqp_server():
    amqp_in_role = 'cfgm'
    rabbit_vip = get_contrail_internal_vip()
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        amqp_in_role = 'openstack'
        rabbit_vip = get_openstack_internal_vip()
    return get_from_testbed_dict('openstack','amqp_host',
        (rabbit_vip or hstr_to_ip(get_control_host_string(env.roledefs[amqp_in_role][0]))))

def get_contrail_amqp_server():
    internal_vip = get_contrail_internal_vip()
    return (internal_vip or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0])))

def get_quantum_service_protocol():
    return get_from_testbed_dict('neutron', 'protocol', 'http')
    
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
            client.connect(host, username=user, password=password, timeout=5)
        except Exception,e:
            return False
        return True
    except socket.error as e:
        return False
    s.close()


import paramiko
from netaddr import *

from fabfile.config import testbed
from fabric.context_managers import settings
from fabric.api import env, run

def hstr_to_ip(host_string):
    return host_string.split('@')[1]

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

def get_service_token():
    service_token = getattr(testbed, 'service_token', '')
    testbed.service_token = get_from_testbed_dict('openstack','service_token',
                             service_token)
    return testbed.service_token

def get_service_token_opt():
    service_token = get_service_token()
    if service_token:
        return '--service_token %s' % (service_token)
    else:
        return ''

def get_haproxy_opt():
    testbed.haproxy = getattr(testbed, 'haproxy', False)
    haproxy_opt = '--haproxy' if testbed.haproxy else ''
    return haproxy_opt

def get_region_name():
    region_name = getattr(testbed, 'region_name', 'RegionOne')
    return get_from_testbed_dict('keystone', 'region_name', region_name)

def get_region_name_opt():
    region_name = get_region_name()
    return '--region_name %s' %(region_name)

def get_keystone_ip():
    svc_opt = ''
    openstack_host = get_control_host_string(testbed.env.roledefs['openstack'][0])
    openstack_ip = hstr_to_ip(openstack_host)
    keystone_ip1 = getattr(testbed, 'keystone_ip', openstack_ip)
    keystone_ip = get_from_testbed_dict('keystone', 'keystone_ip', keystone_ip1)
        
    return keystone_ip

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
    keystone_ip = get_keystone_ip()
    cmd = 'grep "^[ ]*admin_token" /etc/keystone/keystone.conf | tr -d \' \'| awk -F"=" {\'print $2\'}'
    with settings(host_string='root@%s' %(keystone_ip)):
        token = run(cmd)
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

def get_openstack_amqp_server():
    return get_from_testbed_dict('openstack','amqp_host',get_keystone_ip())

def get_quantum_service_protocol():
    return get_from_testbed_dict('neutron', 'protocol', 'http')
    
def verify_sshd(host, user, password):
    try:
        client = paramiko.Transport((host, 22))
        client.connect(username=user, password=password)
    except Exception:
        return False

    client.close()
    return True

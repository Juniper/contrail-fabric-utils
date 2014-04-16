import paramiko
from netaddr import *

from fabfile.config import testbed

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
    svc_opt = ''
    testbed.service_token = getattr(testbed, 'service_token', '')
    if testbed.service_token:
        svc_opt = '--service_token %s' % (testbed.service_token)
    return svc_opt

def get_haproxy_opt():
    testbed.haproxy = getattr(testbed, 'haproxy', False)
    haproxy_opt = '--haproxy' if testbed.haproxy else ''
    return haproxy_opt

def get_region_name():
    region_name = getattr(testbed, 'region_name', 'RegionOne')
    region_name_opt = '--region_name %s' %(region_name)
    return region_name_opt

def get_keystone_ip():
    svc_opt = ''
    openstack_host = get_control_host_string(testbed.env.roledefs['openstack'][0])
    openstack_ip = hstr_to_ip(openstack_host)
    testbed.keystone_ip = getattr(testbed, 'keystone_ip', '')
    if testbed.keystone_ip:
        svc_opt = '--keystone_ip %s' % (testbed.keystone_ip)
    else:
        svc_opt = '--keystone_ip %s' % (openstack_ip)
    return svc_opt

def verify_sshd(host, user, password):
    try:
        client = paramiko.Transport((host, 22))
        client.connect(username=user, password=password)
    except Exception:
        return False

    client.close()
    return True

import os
from netaddr import *

from fabric.api import *

from fabfile.config import testbed
from fabfile.utils.host import hstr_to_ip
from fabric.exceptions import CommandTimeout

@task
def copy_dir(dir_name, tgt_host):
    user_home = os.path.expanduser('~')
    remote_dir = "~/%s" % dir_name.replace(user_home,'')
    for elem in os.listdir(dir_name):
        if elem.startswith('.git'):
            continue
        with settings(host_string=tgt_host):
            run('mkdir -p ~/%s' % dir_name.replace(user_home,''))
            put(os.path.join(dir_name, elem), remote_dir)

def get_data_ip(host_str):
    tgt_ip = None
    tgt_gw= None
    data_ip_info = getattr(testbed, 'control_data', None)
    if data_ip_info:
       if host_str in data_ip_info.keys():
           tgt_ip = str(IPNetwork(data_ip_info[host_str]['ip']).ip)
           tgt_gw = data_ip_info[host_str]['gw']
       else:
           tgt_ip = hstr_to_ip(host_str)
    else:
       tgt_ip = hstr_to_ip(host_str)

    return (tgt_ip, tgt_gw)
#end get_data_ip

def get_vlan_tag(device):
    hosts = getattr(testbed, 'control_data', None)
    if hosts:
        for host in hosts.keys():
            if hosts[host]['device'] == device and hosts[host].has_key('vlan'):
                return hosts[host]['vlan']
    return None

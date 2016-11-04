import os
from netaddr import *

from fabric.api import *

from fabfile.config import testbed
from fabric.exceptions import CommandTimeout

@task
def copy_dir(dir_name, tgt_host):
    user_home = os.path.expanduser('~')
    local_hostname = local('hostname -s',capture=True)
    with settings(host_string=tgt_host):
        remote_hostname = sudo('hostname -s')
        remote_home = sudo('pwd')
    print "Remote host is %s" % (remote_hostname)
    remote_dir = "%s" % dir_name.replace(user_home,remote_home)
    if remote_hostname in local_hostname:
        try:
            if os.path.samefile(remote_dir, dir_name):
                print "No need to copy since source and dest folders are same"
                return
        except OSError,e:
            pass
    for elem in os.listdir(dir_name):
        if elem.startswith('.git'):
            continue
        with settings(host_string=tgt_host):
            sudo('mkdir -p ~/%s' % dir_name.replace(user_home,''))
            put(local_path=os.path.join(dir_name, elem),
                remote_path=remote_dir, mirror_local_mode=True, use_sudo=True)

def get_data_ip(host_str):
    tgt_ip = None
    tgt_gw= None
    data_ip_info = getattr(testbed, 'control_data', None)
    if data_ip_info:
       if host_str in data_ip_info.keys():
           tgt_ip = str(IPNetwork(data_ip_info[host_str]['ip']).ip)
           tgt_gw = data_ip_info[host_str]['gw']
       else:
           tgt_ip = host_str.split('@')[1]
    else:
       tgt_ip = host_str.split('@')[1]

    return (tgt_ip, tgt_gw)
#end get_data_ip

def get_vlan_tag(device, host):
    hosts = getattr(testbed, 'control_data', None)
    if hosts and host in hosts:
        if hosts[host]['device'] == device and hosts[host].has_key('vlan'):
            return hosts[host]['vlan']
    return None

from fabric.api import env, settings, run

from fabos import detect_ostype, get_release, get_build
from fabfile.config import *

def get_orchestrator():
    return getattr(env, 'orchestrator', 'openstack')

def is_lbaas_enabled():
    if 'enable_lbaas' not in env.keys():
        return False
    else:
        return env.enable_lbaas

def get_vgw_details(compute_host_string):
    # Check and collect the VGW details for given compute host
    set_vgw = False
    vgw_intf_list = []
    public_subnet = []
    public_vn_name = []
    gateway_routes = []
    vgw_details = (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list)
    if ('vgw' not in env.roledefs or
        compute_host_string not in env.roledefs['vgw']):
        return vgw_details

    set_vgw = True
    vgw_intf_list = env.vgw[compute_host_string].keys()
    for vgw_intf in vgw_intf_list:
        public_subnet.append(env.vgw[compute_host_string][vgw_intf]['ipam-subnets'])
        public_vn_name.append(env.vgw[compute_host_string][vgw_intf]['vn'])
        if 'gateway-routes' in env.vgw[compute_host_string][vgw_intf].keys():
            gateway_routes.append(env.vgw[compute_host_string][vgw_intf]['gateway-routes'])

    vgw_details = (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list)
    return vgw_details

def get_vmware_details(compute_host_string):
    esxi_data = {}
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if esxi_info:
        for host in esxi_info.keys():
            esxi_data = esxi_info[host]
            data = esxi_data['contrail_vm']
            if (esxi_data['contrail_vm']['host'] == compute_host_string):
                 return esxi_data
            else:
                 continue 
    return None 

def get_esxi_ssl_thumbprint(esxi_data):
    host_string = '%s@%s' %(esxi_data['username'], esxi_data['ip'])
    with settings(host_string = host_string, password = esxi_data['password'],
                    warn_only = True, shell = '/bin/sh -l -c'):
          out = run('openssl x509 -in /etc/vmware/ssl/rui.crt -fingerprint -sha1 -noout')
          out = out.split()
          out = out[7].split('=')
          ssl_thumbprint = out[1]
          print 'ssl thumbprint of the ESXi host %s is %s' % (esxi_data['ip'], ssl_thumbprint)
    return ssl_thumbprint

def get_esxi_vms_and_hosts(esxi_info, vcenter_info, host_list):
    hosts = []
    vms = []
    clusters = []
    for host in host_list:
         with settings(host=host):
               if host in esxi_info.keys():
                   esxi_data = esxi_info[host]
                   vm_name = "ContrailVM"
                   ssl_thumbprint = get_esxi_ssl_thumbprint(esxi_data)
                   esx_list=esxi_data['ip'],esxi_data['username'],esxi_data['password'],ssl_thumbprint,esxi_data['cluster']
                   hosts.append(esx_list)
                   modified_vm_name = vm_name+"-"+vcenter_info['datacenter']+"-"+esxi_data['ip']
                   vms.append(modified_vm_name)
               else: 
                   print 'Info: esxi_hosts block does not have the esxi host.Exiting'
                   return
    clusters = vcenter_info['cluster']
    return (hosts,clusters,vms)

def get_nodes_to_upgrade_pkg(package, os_type, *args, **kwargs):
    """get the list of nodes in which th given package needs to be upgraded"""
    nodes = []
    version = kwargs.get('version', None)
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            act_os_type = detect_ostype()
            if act_os_type == os_type:
                installed = run("dpkg -l | grep %s" % package)
                if not installed:
                    nodes.append(host_string)
                elif (version and
                      version != '%s-%s' %
                         (get_release(package), get_build(package))):
                    nodes.append(host_string)
                else:
                    print 'Required package %s installed. Skipping!' % package
            else:
                raise RuntimeError('Actual OS Type (%s) != Expected OS Type (%s)'
                                    'Aborting!' % (act_os_type, os_type))
    return nodes

def reboot_nodes(*args):
    """reboots the given nodes"""
    for host_string in args:
        with settings(host_string=host_string):
            print "Rebooting (%s) to boot with new kernel version" % host_string
            try:
                sudo('sync; reboot --force', timeout=3)
            except CommandTimeout:
                pass

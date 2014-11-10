from fabfile.config import testbed
from fabric.api import env


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
    vmware = False
    esxi_data = {}
    vmware_info = {}
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if esxi_info:
        for host in esxi_info.keys():
            esxi_data = esxi_info[host]
            data = esxi_data['contrail_vm']
            if (esxi_data['contrail_vm'] == compute_host_string):
                vmware = True
                break

    compute_vm_info = getattr(testbed, 'compute_vm', None)
    if compute_vm_info:
        hosts = compute_vm_info.keys()
        if compute_host_string in hosts:
            vmware = True
            vmware_info = compute_vm_info[compute_host_string]

    return (vmware, esxi_data, vmware_info)

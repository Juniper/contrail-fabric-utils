
_esxi_defaults = {
    'vm_port_group' : 'contrail-vm-pg',
    'fabric_port_group' : 'contrail-fab-pg',
    'fabric_vswitch' : 'vSwitch0',
    'vm_vswitch' : 'vSwitch1',
    'vm_vswitch_mtu' : '9000',
    'uplink_nic' : None,
    'username' : None,
    'password' : None,
    'ip' : None,
    'datastore' : '/vmfs/volumes/datastore1/'
}

_compute_vm_defaults = {
    'name' : 'computevm',
    'mac' : None,
    'host' : None,
    'vmdk' : None
}

def apply_esxi_defaults(esxi_info):
    for k,v in _esxi_defaults.items():
        esxi_info.setdefault(k, v)
    for k,v in _compute_vm_defaults.items():
        esxi_info['contrail_vm'].setdefault(k, v)


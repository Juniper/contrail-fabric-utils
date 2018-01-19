from fabric.api import env

os_username = 'admin'
os_password = '<Password value>'
os_tenant_name = 'demo'

host1 = 'root@1.1.1.1'
host2 = 'root@1.1.1.2'
host3 = 'root@1.1.1.3'
host4 = 'root@1.1.1.4'
host5 = 'root@1.1.1.5'
esx1 = 'root@1.1.1.10'
esx2 = 'root@1.1.1.11'

ext_routers = [('hooper', '1.1.1.253')]
router_asn = 64512
public_vn_rtgt = 2223
public_vn_subnet = "1.1.1.100/28"

host_build = 'root@1.1.1.6'

env.roledefs = {
    'all': [host1, host2, host3, host4, host5],
    'cfgm': [host1, host2],
    'openstack': [host1],
    'control': [host2, host3 ],
    'compute': [host4, host5],
    'collector': [host2, host3],
    'webui': [host1],
    'database': [host1, host2, host3],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodei1', 'nodei2', 'nodei3', 'nodei4-compute-vm', 'nodei5-compute-vm']
}

control_data = {
    host1 : { 'ip': 'x.x.x.1/24', 'gw' : 'x.x.x.254', 'device':'eth3' },
    host2 : { 'ip': 'x.x.x.2/24', 'gw' : 'x.x.x.254', 'device':'eth3' },
    host3 : { 'ip': 'x.x.x.3/24', 'gw' : 'x.x.x.254', 'device':'eth3' },
    host4 : { 'ip': 'x.x.x.4/24', 'gw' : 'x.x.x.254', 'device':'eth2' },
    host5 : { 'ip': 'x.x.x.5/24', 'gw' : 'x.x.x.254', 'device':'eth2' },
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
    host3:'ubuntu',
    host4:'ubuntu',
    host5:'ubuntu',
}
env.password = '<Password value>'
env.passwords = {
    host1: '<Password value>',
    host2: '<Password value>',
    host3: '<Password value>',
    host4: '<Password value>',
    host5: '<Password value>',
    esx1: '<Password value>',
    esx2: '<Password value>',

    host_build: '<Password value>',
}

esxi_hosts = {
    'nodei4' : {
        'ip' : '1.1.1.4',
        'username' : 'root',
        'password' : '<Password value>',
        'uplink_nic' : 'vmnic0',
        'fabric_vswitch' : 'vSwitch0',
        'fabric_port_group' : 'contrail-fab-pg',
        'vm_vswitch' : 'vSwitch1',
        'vm_vswitch_mtu' : '9000',
        'vm_port_group' : 'contrail-vm-pg',
        'data_port_group' : 'contrail-data-pg',
        'data_nic' : 'vmnic3',
        'data_vswitch' : 'vSwitch2',
        'datastore' : '/vmfs/volumes/datastore1/',
        'contrail_vm' : {
            'name' : 'nodei4-compute-vm',
            'mac' : 'aa:dd:ff:aa:aa:aa',
            'host' : host4,
            'vmdk' : '/cs-shared-test/images/Ubuntu-precise-12.04.3-LTS.vmdk',
        }
    },
    'nodei5' : {
        'ip' : '1.1.1.5',
        'username' : 'root',
        'password' : '<Password value>',
        'uplink_nic' : 'vmnic0',
        'fabric_vswitch' : 'vSwitch0',
        'fabric_port_group' : 'contrail-fab-pg',
        'vm_vswitch' : 'vSwitch1',
        'vm_vswitch_mtu' : '9000',
        'vm_port_group' : 'contrail-vm-pg',
        'data_port_group' : 'contrail-data-pg',
        'data_nic' : 'vmnic3',
        'data_vswitch' : 'vSwitch2',
        'datastore' : '/vmfs/volumes/datastore1/',
        'contrail_vm' : {
            'name' : 'nodei5-compute-vm',
            'mac' : 'aa:cc:de:aa:aa:ab',
            'host' : host5,
            'vmdk' : '/cs-shared-test/images/Ubuntu-precise-12.04.3-LTS.vmdk',
        }
    }
}
multi_tenancy=True
env.interface_rename = False
env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"
env.enable_lbaas = True

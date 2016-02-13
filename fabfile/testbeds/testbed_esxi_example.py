from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.204.217.113'
host2 = 'root@10.204.217.114'
host3 = 'root@10.204.217.115'
host4 = 'root@10.204.217.181'
host5 = 'root@10.204.217.182'
esx1 = 'root@10.204.217.116'
esx2 = 'root@10.204.217.117'

ext_routers = [('hooper', '192.168.192.253')]
router_asn = 64512
public_vn_rtgt = 2223
public_vn_subnet = "10.204.221.176/28"

host_build = 'stack@10.204.216.49'

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
    host1 : { 'ip': '192.168.192.1/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host2 : { 'ip': '192.168.192.2/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host3 : { 'ip': '192.168.192.3/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host4 : { 'ip': '192.168.192.4/24', 'gw' : '192.168.192.254', 'device':'eth2' },
    host5 : { 'ip': '192.168.192.5/24', 'gw' : '192.168.192.254', 'device':'eth2' },
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
    host3:'ubuntu',
    host4:'ubuntu',
    host5:'ubuntu',
}
env.password = 'c0ntrail123'
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',
    esx1: 'c0ntrail123',
    esx2: 'c0ntrail123',

    host_build: 'stack@123',
}

esxi_hosts = {
    'nodei4' : {
        'ip' : '10.204.217.116',
        'username' : 'root',
        'password' : 'c0ntrail123',
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
            'mac' : '00:50:56:aa:aa:aa',
            'host' : host4,
            'vmdk' : '/cs-shared-test/images/Ubuntu-precise-12.04.3-LTS.vmdk',
        }
    },
    'nodei5' : {
        'ip' : '10.204.217.117',
        'username' : 'root',
        'password' : 'c0ntrail123',
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
            'mac' : '00:50:56:aa:aa:ab',
            'host' : host5,
            'vmdk' : '/cs-shared-test/images/Ubuntu-precise-12.04.3-LTS.vmdk',
        }
    }
}
multi_tenancy=True
env.interface_rename = False
env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"
env.enable_lbaas = True

#env.optional_services = {
#    'collector': ['snmp-collector', 'topology'],
#    'cfgm'     : ['device-manager'],
#}

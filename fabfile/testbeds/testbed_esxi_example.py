from fabric.api import env

nodea22     = '10.204.216.18'
nodea7      = '10.204.216.45'
contrailvm2 = '10.204.217.180'
host1 = 'root@' + nodea22
host2 = 'root@' + contrailvm2
host3 = 'root@' + nodea7

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

ext_routers = []
router_asn = 64512
public_vn_rtgt = 10003
public_vn_subnet = '10.204.219.64/29'

host_build = 'sunilbasker@10.204.216.56'

env.roledefs = {
    'all': [host1, host2, host3],
    'cfgm': [host1],
    'control': [host1],
    'compute': [host1, host2, host3],
    'collector': [host1],
    'webui': [host1],
    'database': [host1],
    'openstack': [host1],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodea22', 'ContrailVM2', 'nodea7']
}

env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

env.ostypes = {
   host1 : 'ubuntu',
   host2 : 'ubuntu',
   host3 : 'ubuntu',
}

esxi_hosts = {
    'esxi_host1' : {
          'ip' : '10.204.217.105',
          'username' : 'root',
          'password' : 'c0ntrail123',
          'uplink_nic' : 'vmnic0',
          'fabric_vswitch' : 'vSwitch0',
          'fabric_port_group' : 'contrail-fab-pg',
          'vm_vswitch' : 'vSwitch1',
          'vm_port_group' : 'contrail-vm-pg',
          'datastore' : '/vmfs/volumes/datastore1/',
          'contrail_vm' : {
               'name' : 'ContrailVM2',
               'mac' : '00:50:56:aa:ab:ad',
               'host' : host2,
               'vmdk' : '/cs-shared-test/images/Ubuntu-precise-12.04.3-LTS.vmdk'
          }
    }
}


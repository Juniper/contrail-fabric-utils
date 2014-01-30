from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.204.217.6'
host2 = 'root@10.204.217.4'
host3 = 'root@10.204.217.5'
host4 = 'root@10.204.217.101'
host5 = 'root@10.204.217.102'
host6 = 'root@10.204.217.3'

ext_routers = [('blr-mx1', '10.204.216.253')]
router_asn = 64512
public_vn_rtgt = 10003
public_vn_subnet = '10.204.219.16/29'

host_build = 'stack@10.204.216.49'

env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6],
    'cfgm': [host1, host2, host3],
    'openstack': [host2],
    'webui': [host3],
    'control': [host1, host3],
    'compute': [host4, host5, host6],
    'collector': [host1, host3],
    'database': [host1],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodec21', 'nodec19', 'nodec20', 'nodec61', 'nodec62','nodec18']
}

env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',
    host6: 'c0ntrail123',

    host_build: 'c0ntrail123',
}

env.ostypes = {
    host1: 'fedora',
    host2: 'fedora',
    host3: 'fedora',
    host4: 'fedora',
    host5: 'fedora',
    host6: 'fedora',
}

env.test_repo_dir = "/home/stack/multi_node/contrail-test"
env.mail_from='vjoshi@juniper.net'
env.mail_to='dl-contrail-sw@juniper.net'
env.log_scenario='Fedora Openstack Five-Node Sanity'
multi_tenancy=True
env.interface_rename = False
env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"

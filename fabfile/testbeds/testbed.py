from fabric.api import env

host1 = 'root@10.204.220.117'
host2 = 'root@10.204.220.118'
host3 = 'root@10.204.220.116'
host4 = 'root@10.204.216.48'

ext_routers = [('blr-mx2', '10.204.216.245')]
router_asn = 64512
public_vn_rtgt = 20001
public_vn_subnet = "10.204.220.176/29"

host_build = 'hkumar@10.204.216.3'

env.roledefs = {
    'all': [host1, host2, host3, host4],
    'cfgm': [host1, host2, host3],
    'openstack': [host2],
    'control': [host2, host3],
    'compute': [host4],
    'collector': [host1],
    'webui': [host1],
    'database': [host1, host2, host3],
    'build': [host_build],
}

env.virtual_nodes_info = {
    host1: {
        'keystone_ip': '10.204.217.119',
        'keystone_authip': '192.168.22.2',
        'keystone_user': 'root',
        'keystone_pass': 'c0ntrail123',
        'user': 'admin',
        'password': 'contrail123',
        'tenant': 'admin',
        'tenant_id': '81559c49f9d24ed28676036135856562',
        'image_name': '653310d6-1c7f-4f2a-9c8d-6a1746f26bb3',
        'flavor': '3',
        'vn_id': 'f0cd51f0-8be8-4ccf-bc07-cf96fe85f325',
        'mac-address': '07:af:b6:a7:33:c6',
    },
    host2: {
        'keystone_ip': '10.204.217.119',
        'keystone_authip': '192.168.22.2',
        'keystone_user': 'root',
        'keystone_pass': 'c0ntrail123',
        'user': 'admin',
        'password': 'contrail123',
        'tenant': 'admin',
        'tenant_id': '81559c49f9d24ed28676036135856562',
        'image_name': '653310d6-1c7f-4f2a-9c8d-6a1746f26bb3',
        'flavor': '3',
        'vn_id': 'f0cd51f0-8be8-4ccf-bc07-cf96fe85f325',
        'mac-address': '07:af:b6:a7:33:c7',
    },
    host3: {
        'keystone_ip': '10.204.217.119',
        'keystone_authip': '192.168.22.2',
        'keystone_user': 'root',
        'keystone_pass': 'c0ntrail123',
        'user': 'admin',
        'password': 'contrail123',
        'tenant': 'admin',
        'tenant_id': '81559c49f9d24ed28676036135856562',
        'image_name': '653310d6-1c7f-4f2a-9c8d-6a1746f26bb3',
        'flavor': '3',
        'vn_id': 'f0cd51f0-8be8-4ccf-bc07-cf96fe85f325',
        'mac-address': '07:af:b6:a7:33:c8',
    },
}

env.hostnames = {
    'all': ['testvm1', 'testvm2', 'testvm3', 'nodea10']
}

env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    # host5: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

env.password = 'c0ntrail123'

env.ostypes = {
    host1: 'ubuntu',
    host2: 'ubuntu',
    host3: 'ubuntu',
    host4:'ubuntu',
    # host5:'ubuntu',
}
env.test_repo_dir = '/homes/hkumar/contrail-test'
env.mail_from = 'hkumar@juniper.net'
env.mail_to = 'hkumar@juniper.net'

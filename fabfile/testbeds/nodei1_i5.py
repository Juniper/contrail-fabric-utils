from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.204.217.113'
host2 = 'root@10.204.217.114'
host3 = 'root@10.204.217.115'
host4 = 'root@10.204.217.116'
host5 = 'root@10.204.217.117'

ext_routers = [('hooper', '192.168.192.254')]
router_asn = 64512
public_vn_rtgt = 10000
public_vn_subnet = "10.84.46.0/24"

host_build = 'stack@10.204.216.49'

env.roledefs = {
    'all': [host1, host2, host3, host4, host5],
    'cfgm': [host1,host2],
    'openstack': [host1],
    'control': [host2, host3 ],
    'compute': [host4,host5],
    'collector': [host2,host3],
    'webui': [host1],
    'database': [host1,host2,host3],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodei1', 'nodei2', 'nodei3','nodei4', 'nodei5']
}

control_data = {
    host1 : { 'ip': '192.168.192.1/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host2 : { 'ip': '192.168.192.2/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host3 : { 'ip': '192.168.192.3/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host4 : { 'ip': '192.168.192.4/24', 'gw' : '192.168.192.254', 'device':'eth3' },
    host5 : { 'ip': '192.168.192.5/24', 'gw' : '192.168.192.254', 'device':'eth3' },
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
    host3:'ubuntu',
    host4:'ubuntu',
    host5:'ubuntu',
}
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',

    host_build: 'stack@123',
}

env.test_repo_dir='/home/stack/multi_interface_parallel/ubuntu/icehouse/contrail-test'
env.mail_from='contrail-build@juniper.net'
env.mail_to='dl-contrail-sw@juniper.net'
env.log_scenario='Ubuntu five-Node Parallel Sanity-multi-interface'
multi_tenancy=True
env.interface_rename = False
env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"

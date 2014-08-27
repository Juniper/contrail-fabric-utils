from fabric.api import env

host1 = 'root@10.84.13.32'
host2 = 'root@10.84.13.33'
host3 = 'root@10.84.13.38'
host4 = 'root@10.84.13.19'
host5 = 'root@10.84.13.22'

ext_routers = []
router_asn = 64512
#public_vn_rtgt = 10003
#public_vn_subnet = "10.204.219.32/29"

host_build = 'stack@10.84.24.64'

env.roledefs = {
    'all': [host1, host2, host3, host4, host5],
    'cfgm': [host1, host2],
    'openstack': [host2],
    'control': [host2, host3],
    'compute': [host4, host5],
    'collector': [host1],
    'webui': [host1],
    'database': [host1, host2, host3],
    'build': [host_build],
}

env.hostnames = {
    'all': ['a6s32', 'a6s33', 'a6s38', 'a6s19', 'a6s22']
}

env.password = 'c0ntrail123'
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',

    host_build: 'contrail123',
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
    host3:'ubuntu',
    host4:'ubuntu',
    host5:'ubuntu',
}
control_data= {

    host1 : { 'ip': '192.168.10.1/24', 'gw' : '192.168.10.254', 'device':'eth0' },
    host2 : { 'ip': '192.168.10.2/24', 'gw' : '192.168.10.254', 'device':'eth0' },
    host3 : { 'ip': '192.168.10.3/24', 'gw' : '192.168.10.254', 'device':'eth0' },
    host4 : { 'ip': '192.168.10.4/24', 'gw' : '192.168.10.254', 'device':'eth0' },
    host5 : { 'ip': '192.168.10.5/24', 'gw' : '192.168.10.254', 'device':'eth0' },
}

env.test_repo_dir="/home/stack/multi_interface-ubuntu/contrail-test"
env.mail_from='vjoshi@juniper.net'
env.mail_to='dl-contrail-sw@juniper.net'
multi_tenancy=True
env.encap_priority="'MPLSoUDP','MPLSoGRE','VXLAN'"
env.mail_server='10.84.24.64'
env.mail_port='4000'
env.log_scenario='Ubuntu-Havana Five-Node Sanity[Multi Intface]'

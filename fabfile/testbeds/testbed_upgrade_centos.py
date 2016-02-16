import os
from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.84.14.44'
host2 = 'root@10.84.14.45'
host3 = 'root@10.84.14.46'
host4 = 'root@10.84.14.53'
host5 = 'root@10.84.14.54'
host6 = 'root@10.84.14.55'
host7 = 'root@10.84.14.56'
host8 = 'root@10.84.14.57'

ext_routers = []
router_asn = 64512
public_vn_rtgt = 10000
public_vn_subnet = "10.84.44.0/24"

host_build = 'stack@10.84.24.64'

env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6, host7, host8],
    'cfgm': [host1, host2, host3],
    'control': [host2, host3],
    'compute': [host7, host8],
    'collector': [host4, host5, host6],
    'database': [host4, host5, host6],
    'webui': [host1],
    'openstack': [host1],
    'build': [host_build],
}

env.hostnames = {
    'all': ['a5s164', 'a5s165', 'a5s166','a5s193', 'a5s194', 'a5s195', 'a5s196', 'a5s197']
}


env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',
    host6: 'c0ntrail123',
    host7: 'c0ntrail123',
    host8: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

env.ostypes = {
    host1: 'centos',
    host2: 'centos',
    host3: 'centos',
    host4: 'centos',
    host5: 'centos',
    host6: 'centos',
    host7: 'centos',
    host8: 'centos',
}

env.encap_priority="'MPLSoUDP','MPLSoGRE','VXLAN'"
multi_tenancy=True
do_parallel =True
env.mail_port='4000'
env.mail_server='10.84.24.64'
env.test_repo_dir="/home/stack/upgrade_sanity/contrail-test"
env.log_scenario='Centos-Upgrade Sanity'
env.mail_from='ijohnson@juniper.net'
env.mail_to='dl-contrail-sw@juniper.net'

#env.optional_services = {
#    'collector': ['snmp-collector', 'topology'],
#    'cfgm'     : ['device-manager'],
#}

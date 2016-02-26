from fabric.api import env

host1 = 'root@10.204.216.60'

ext_routers = [('mx1', '10.204.216.253')]
router_asn = 64510
public_vn_rtgt = 10003
public_vn_subnet = "10.204.219.24/29"

host_build = 'vjoshi@10.204.216.56'

env.roledefs = {
    'all': [host1],
    'cfgm': [host1],
    'openstack': [host1],
    'control': [host1],
    'compute': [host1],
    'collector': [host1],
    'webui': [host1],
    'database': [host1],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodec3']
}

env.passwords = {
    host1: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

env.test_repo_dir='/root/contrail-test'
env.mail_from='vjoshi@juniper.net'
env.mail_to='vjoshi@juniper.net'
env.log_scenario='Vedus single node'
multi_tenancy=True
env.interface_rename = False 
env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"

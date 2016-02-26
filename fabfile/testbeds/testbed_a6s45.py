from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'
multi_tenancy = False

host1 = 'root@10.84.13.45'

ext_routers = []
router_asn = 64512
public_vn_rtgt = 10000
public_vn_subnet = "10.84.41.0/24"

host_build = 'root@10.84.13.45'

env.roledefs = {
    'all': [host1],
    'cfgm': [host1],
    'collector': [host1],
    'openstack': [host1],
    'webui': [host1],
    'control': [host1],
    'compute': [host1],
    'database': [host1],
    'build': [host_build],
}
env.hostnames = {
    'all': ['a6s45']
}

env.passwords = {
    host1: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

env.ostypes = {
    host1:'centos'
}

env.test_repo_dir='/users/rajreddy/test/git-test/'
env.mail_from='rajreddy@juniper.net'
env.mail_to='rajreddy@juniper.net'


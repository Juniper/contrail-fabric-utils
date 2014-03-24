from fabric.api import env

host1 = 'root@10.204.217.65'
#host1 = 'root@10.204.216.24'
host_build = 'vvelpula@10.204.216.56'
ext_routers = []
router_asn = 64512
env.devstack = 0
#public_vn_rtgt = 10003
#public_vn_subnet = "10.204.219.72/28"
env.roledefs = {
   'all':[host1],
   'cfgm':[host1],
   'openstack':[host1],
   'webui':[host1],
   'control':[host1],
   'compute':[host1],
   'collector':[host1],
   'database':[host1],
   'build':[host1],
}
env.hostnames = {
   'all':['nodea28']
}
env.ostypes = {
    host1: 'ubuntu',
}
env.passwords = {
    host1: 'c0ntrail123',
    host_build: 'secret',
}
env.test_repo_dir = '/home/vvelpula/github_24_03/contrail-test'
env.mail_from = 'vvelpula@juniper.net'
env.mail_to = 'vvelpula@juniper.net'

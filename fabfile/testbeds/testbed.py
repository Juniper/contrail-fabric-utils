from fabric.api import env

env.test_repo_dir = '/users/ijohnson/github/R1.10/contrail-test'
#Management ip addresses of hosts in the cluster
host1 = 'root@10.84.14.44'
host2 = 'root@10.84.14.45'
host3 = 'root@10.84.14.46'
host4 = 'root@10.84.14.53'
host5 = 'root@10.84.14.54'
host6 = 'root@10.84.14.55'
host7 = 'root@10.84.14.56'
host8 = 'root@10.84.14.57'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '10.204.216.253')]
ext_routers = []

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'ijohnson@10.84.5.31'

#Role definition of the hosts.
env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6, host7, host8],
    'cfgm': [host1, host2, host3],
    'openstack': [host4, host5, host6],
    'control': [host1, host3],
    'compute': [host7, host8],
    'collector': [host1, host3],
    'webui': [host3],
    'database': [host1, host2, host3],
    'build': [host_build],
}

env.password = 'c0ntrail123'
#Passwords of each host
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',
    host6: 'c0ntrail123',
    host7: 'c0ntrail123',
    host8: 'c0ntrail123',
    host_build: 'ijohnson123',
}

#For reimage purpose
env.ostypes = {
    host1: 'ubuntu',
    host2: 'ubuntu',
    host3: 'ubuntu',
    host4: 'ubuntu',
    host5: 'ubuntu',
    host6: 'ubuntu',
    host7: 'ubuntu',
    host8: 'ubuntu',
}

env.openstack = {
    'manage_amqp' : 'yes'
}

env.ha = {
    'internal_vip' : '10.84.14.200',
    'contrail_internal_vip' : '10.84.14.201'
}

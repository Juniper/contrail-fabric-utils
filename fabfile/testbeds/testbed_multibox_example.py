from fabric.api import env

#Management ip addresses of hosts in the cluster
host1 = 'root@1.1.1.1'
host2 = 'root@1.1.1.2'
host3 = 'root@1.1.1.3'
host4 = 'root@1.1.1.4'
host5 = 'root@1.1.1.5'
host6 = 'root@1.1.1.6'
host7 = 'root@1.1.1.7'
host8 = 'root@1.1.1.8'
host9 = 'root@1.1.1.9'
host10 = 'root@1.1.1.10'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '10.204.216.253')]
ext_routers = []

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'root@1.1.1.1'

#Role definition of the hosts.
env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6, host7, host8, host9, host10],
    'cfgm': [host1, host2, host3],
    'openstack': [host1],
    'control': [host1, host2, host3],
    'compute': [host4, host5, host6, host7, host8, host9, host10],
    'collector': [host1, host2, host3],
    'webui': [host1],
    'database': [host1, host2, host3],
    'build': [host_build],
    'storage-master': [host1],
    'storage-compute': [host4, host5, host6, host7, host8, host9, host10],
}

env.hostnames = {
    'all': ['a0s1', 'a0s2', 'a0s3','a0s4', 'a0s5', 'a0s6', 'a0s7', 'a0s8', 'a0s9', 'a0s10']
}

#Openstack admin password
env.openstack_admin_password = 'secret123'

env.password = 'secret'
#Passwords of each host
env.passwords = {
    host1: 'secret',
    host2: 'secret',
    host3: 'secret',
    host4: 'secret',
    host5: 'secret',
    host6: 'secret',
    host7: 'secret',
    host8: 'secret',
    host9: 'secret',
    host10: 'secret',

    host_build: 'secret',
}

#For reimage purpose
env.ostypes = {
    host1: 'centos',
    host2: 'centos',
    host3: 'centos',
    host4: 'centos',
    host5: 'centos',
    host6: 'centos',
    host7: 'centos',
    host8: 'centos',
    host9: 'centos',
    host10: 'centos',
}

#OPTIONAL ANALYTICS CONFIGURATION
#================================
# database_dir is the directory where cassandra data is stored
#
# If it is not passed, we will use cassandra's default
# /var/lib/cassandra/data
#
#database_dir = '<separate-partition>/cassandra'
#
# analytics_data_dir is the directory where cassandra data for analytics
# is stored. This is used to seperate cassandra's main data storage [internal
# use and config data] with analytics data. That way critical cassandra's 
# system data and config data are not overrun by analytis data
#
# If it is not passed, we will use cassandra's default
# /var/lib/cassandra/data
#
#analytics_data_dir = '<separate-partition>/analytics_data'
#
# ssd_data_dir is the directory where cassandra can store fast retrievable
# temporary files (commit_logs). Giving cassandra an ssd disk for this
# purpose improves cassandra performance
#
# If it is not passed, we will use cassandra's default
# /var/lib/cassandra/commit_logs
#
#ssd_data_dir = '<seperate-partition>/commit_logs_data'

#OPTIONAL BONDING CONFIGURATION
#==============================
#Inferface Bonding
#bond= {
#    host2 : { 'name': 'bond0', 'member': ['p2p0p0','p2p0p1','p2p0p2','p2p0p3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
#    host5 : { 'name': 'bond0', 'member': ['p4p0p0','p4p0p1','p4p0p2','p4p0p3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
#}

#OPTIONAL SEPARATION OF MANAGEMENT AND CONTROL + DATA and OPTIONAL VLAN INFORMATION
#==================================================================================
#control_data = {
#    host1 : { 'ip': '192.168.10.1/24', 'gw' : '192.168.10.254', 'device':'eth0', 'vlan': '224' },
#    host2 : { 'ip': '192.168.10.2/24', 'gw' : '192.168.10.254', 'device':'bond0', 'vlan': '224' },
#    host3 : { 'ip': '192.168.10.3/24', 'gw' : '192.168.10.254', 'device':'eth0', 'vlan': '224' },
#    host4 : { 'ip': '192.168.10.4/24', 'gw' : '192.168.10.254', 'device':'eth3', 'vlan': '224' },
#    host5 : { 'ip': '192.168.10.5/24', 'gw' : '192.168.10.254', 'device':'bond0', 'vlan': '224' },
#    host6 : { 'ip': '192.168.10.6/24', 'gw' : '192.168.10.254', 'device':'eth0', 'vlan': '224' },
#    host7 : { 'ip': '192.168.10.7/24', 'gw' : '192.168.10.254', 'device':'eth1', 'vlan': '224' },
#    host8 : { 'ip': '192.168.10.8/24', 'gw' : '192.168.10.254', 'device':'eth1', 'vlan': '224' },
#}

#OPTIONAL STATIC ROUTE CONFIGURATION
#===================================
#static_route  = {
#    host2 : [{ 'ip': '10.1.1.0', 'netmask' : '255.255.255.0', 'gw':'192.168.10.254', 'intf': 'bond0' },
#             { 'ip': '10.1.2.0', 'netmask' : '255.255.255.0', 'gw':'192.168.10.254', 'intf': 'bond0' }],
#    host5 : [{ 'ip': '10.1.1.0', 'netmask' : '255.255.255.0', 'gw':'192.168.10.254', 'intf': 'bond0' }],
#}

#storage compute disk config
#storage_node_config = {
#    host4 : { 'disks' : ['sdc', 'sdd'] },
#    host5 : { 'disks' : ['sdc', 'sdd'] },
#    host6 : { 'disks' : ['sdc', 'sdd'] },
#}

#live migration config
#live_migration = True

#ceph_nfs_livem = True
#ceph_nfs_livem_subnet = '192.168.10.253/24'
#ceph_nfs_livem_image = '/ubuntu/livemnfs.qcow2'
#ceph_nfs_livem_host = 'host4'

#To disable installing contrail interface rename package
#env.interface_rename = False

#In environments where keystone is deployed outside of Contrail provisioning
#scripts , you can use the below options 
#
# Note : 
# "insecure" is applicable only when protocol is https
# The entries in env.keystone overrides the below options which used
# to be supported earlier :
#  service_token
#  keystone_ip
#  keystone_admin_user
#  keystone_admin_password
#  region_name
#
#env.keystone = {
#    'keystone_ip'   : 'x.y.z.a',
#    'auth_protocol' : 'http',                  #Default is http
#    'auth_port'     : '35357',                 #Default is 35357
#    'admin_token'   : '33c57636fbc2c5552fd2',  #admin_token in keystone.conf
#    'admin_user'    : 'admin',                 #Default is admin
#    'admin_password': 'contrail123',           #Default is contrail123
#    'service_tenant': 'service',               #Default is service
#    'admin_tenant'  : 'admin',                 #Default is admin
#    'region_name'   : 'RegionOne',             #Default is RegionOne
#    'insecure'      : 'True',                  #Default = False
#}
#

# In environments where openstack services are deployed independently 
# from contrail, you can use the below options 
# service_token : Common service token for for all services like nova,
#                 neutron, glance, cinder etc
# amqp_host     : IP of AMQP Server to be used in openstack
#
#env.openstack = {
#    'service_token' : '33c57636fbc2c5552fd2', 
#    'amqp_host' : '10.204.217.19',
#}

#To enable multi-tenancy feature
#multi_tenancy = True

#To enable haproxy feature
#haproxy = True

#To Enable prallel execution of task in multiple nodes
#do_parallel = True

# To configure the encapsulation priority. Default: MPLSoGRE 
#env.encap_priority =  "'MPLSoUDP','MPLSoGRE','VXLAN'"

# Optional proxy settings.
# env.http_proxy = os.environ.get('http_proxy')

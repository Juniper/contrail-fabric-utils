from fabric.api import env
# DO not use a1s42 - 10.84.5.42
#Management ip addresses of hosts in the cluster
host1 = 'root@10.84.24.11'
host2 = 'root@10.84.24.12'
host3 = 'root@10.84.24.13'
host4 = 'root@10.84.24.14'
host5 = 'root@10.84.24.15'
host6 = 'root@10.84.24.16'
host7 = 'root@10.84.24.17'
host8 = 'root@10.84.24.18'
host9 = 'root@10.84.24.19'
host10 = 'root@10.84.24.20'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '10.204.216.253')]
ext_routers = [('mx1', '192.168.254.1')]
router_asn = 64512
public_vn_rtgt = 1024
public_vn_subnet = "10.84.58.0/24"

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'kparmar@10.84.5.31'

#Role definition of the hosts.
env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6, host7, host8, host9, host10],
    'cfgm': [host1, host2, host3],
    'openstack': [host1],
    'control': [host2, host3],
    'compute': [host4, host5, host6, host7, host8, host9, host10],
    'collector': [host1, host2, host3],
    'webui': [host1],
    'database': [host1, host2, host3],
    'build': [host_build],
    'storage-master': [host1],
    'storage-compute': [host4, host5, host6, host7, host8, host9, host10],
}

env.hostnames = {
    'all': ['b4s11', 'b4s12', 'b4s13', 'b4s14', 'b4s15', 'b4s16', 'b4s17', 'b4s18', 'b4s19', 'b4s20']
}

#Openstack admin password
env.openstack_admin_password = 'c0ntrail123'

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
    host9: 'c0ntrail123',
    host10: 'c0ntrail123',

    host_build: 'c0ntrail123',
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
    host9: 'ubuntu',
    host10: 'ubuntu',
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
bond= {
    host1 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host2 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host3 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host4 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host5 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host6 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host7 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host8 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host9 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
    host10 : { 'name': 'bond0', 'member': ['eth2','eth3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
}

#OPTIONAL SEPARATION OF MANAGEMENT AND CONTROL + DATA and OPTIONAL VLAN INFORMATION
#==================================================================================
#control_data = {
#    host1 : { 'ip': '192.168.250.11/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host2 : { 'ip': '192.168.250.12/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host3 : { 'ip': '192.168.250.13/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host4 : { 'ip': '192.168.250.14/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host5 : { 'ip': '192.168.250.15/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host6 : { 'ip': '192.168.250.16/24', 'gw' : '192.168.250.1', 'device':'eth2'},
#    host7 : { 'ip': '192.168.250.17/24', 'gw' : '192.168.250.1', 'device':'eth2'},
#    host8 : { 'ip': '192.168.250.18/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host9 : { 'ip': '192.168.250.19/24', 'gw' : '192.168.250.1', 'device':'eth3'},
#    host10 : { 'ip': '192.168.250.20/24', 'gw' : '192.168.250.1', 'device':'eth3'}
#}

control_data = {
    host1 : { 'ip': '192.168.250.11/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host2 : { 'ip': '192.168.250.12/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host3 : { 'ip': '192.168.250.13/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host4 : { 'ip': '192.168.250.14/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host5 : { 'ip': '192.168.250.15/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host6 : { 'ip': '192.168.250.16/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host7 : { 'ip': '192.168.250.17/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host8 : { 'ip': '192.168.250.18/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host9 : { 'ip': '192.168.250.19/24', 'gw' : '192.168.250.1', 'device':'bond0'},
    host10 : { 'ip': '192.168.250.20/24', 'gw' : '192.168.250.1', 'device':'bond0'}
}
#OPTIONAL STATIC ROUTE CONFIGURATION
#===================================
static_route  = {
    host1 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host2 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host3 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host4 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host5 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host6 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host7 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host8 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host9 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }],
    host10 : [{ 'ip': '192.168.254.0', 'netmask' : '255.255.255.0', 'gw':'192.168.250.1', 'intf': 'bond0' }]
}

#storage compute disk config
#storage_node_config = {
#    host4 : { 'disks' : ['/dev/sdc', '/dev/sdd'], 'journal' : ['/dev/sde', '/dev/sdf'] },
#    host5 : { 'disks' : ['/dev/sdc:/dev/sde', '/dev/sdd:/dev/sde'], 'ssd-disks' : ['/dev/sdf', '/dev/sdg'] },
#    host6 : { 'disks' : ['/dev/sdc', '/dev/sdd'], 'local-disks' : ['/dev/sde'], 'local-ssd-disks' : ['/dev/sdf'] },
#}
storage_node_config = {
    host4 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host5 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host6 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host7 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host8 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host9 : { 'disks' : ['/dev/sdc'], 'journal' : ['/dev/sdd'] },
    host10 : { 'disks' : ['/dev/sdb'], 'journal' : ['/dev/sdc'] },
}

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

# In High Availability setups.
#env.ha = {
#    'internal_vip'   : '1.1.1.1',               #Internal Virtual IP of the HA setup.
#    'external_vip'   : '2.2.2.2',               #External Virtual IP of the HA setup.
#    'nfs_server'      : '3.3.3.3',               #IP address of the NFS Server which will be mounted to /var/lib/glance/images of openstack Node, Defaults to env.roledefs['compute'][0]
#    'nfs_glance_path' : '/var/tmp/images/',      #NFS Server path to save images, Defaults to /var/tmp/glance-images/
#}

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

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
    # 'vgw': [host4, host5], # Optional, Only to enable VGW. Only compute can support vgw
    # 'tsn': [host10], # Optional, Only to enable TSN. Only compute can support TSN
    # 'toragent': [host10], Optional, Only to enable Tor Agent. Only compute can
    # support Tor Agent
    #   'backup':[backup_node],  # only if the backup_node is defined
}

env.hostnames = {
    'all': ['a0s1', 'a0s2', 'a0s3','a0s4', 'a0s5', 'a0s6', 'a0s7', 'a0s8', 'a0s9', 'a0s10','backup_node']
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
    #  backup_node: 'secret',
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
env.orchestrator = 'openstack' #other values are 'vcenter' default:openstack

# INFORMATION FOR DB BACKUP/RESTORE ..
#=======================================================
#Optional,Backup Host configuration if it is not available then it will put in localhost
#backup_node = 'root@2.2.2.2'

# Optional, Local/Remote location of backup_data path
# if it is not passed then it will use default path
#backup_db_path= ['/home/','/root/']
#cassandra backup can be defined either "full" or "custom"
#full -> take complete snapshot of cassandra DB
#custom -> take snapshot except defined in skip_keyspace
#cassandra_backup='custom'  [ MUST OPTION]
#skip_keyspace=["ContrailAnalytics"]  IF cassandra_backup is selected as custom
#service token need to define to do  restore of backup data
#service_token = '53468cf7552bbdc3b94f'




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

#following variables allow analytics data to have different TTL in cassandra database
#analytics_config_audit_ttl controls TTL for config audit logs
#analytics_statistics_ttl controls TTL for stats
#analytics_flow_ttl controls TTL for flow data
#database_ttl controls TTL for rest of the data
#
#database_ttl = 48
#analytics_config_audit_ttl = 48
#analytics_statistics_ttl = 48
#analytics_flow_ttl = 48

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
#    host4 : { 'disks' : ['/dev/sdc', '/dev/sdd'], 'journal' : ['/dev/sde', '/dev/sdf'] },
#    host5 : { 'disks' : ['/dev/sdc:/dev/sde', '/dev/sdd:/dev/sde'], 'ssd-disks' : ['/dev/sdf', '/dev/sdg'] },
#    host6 : { 'disks' : ['/dev/sdc', '/dev/sdd'], 'local-disks' : ['/dev/sde'], 'local-ssd-disks' : ['/dev/sdf'] },
#}

#live migration config
#live_migration = True

#Enable this for External NFS server
#ext_nfs_livem = True
#ext_nfs_livem_mount = '11.1.0.1:/nfsvol'

#Enable this for Ceph based NFS VM server
#ceph_nfs_livem = True
#ceph_nfs_livem_subnet = '192.168.10.253/24'
#ceph_nfs_livem_image = '/ubuntu/livemnfs.qcow2'
#ceph_nfs_livem_host = host4

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
#    'manage_neutron': 'no',                    #Default = 'yes' , Does configure neutron user/role in keystone required.
#}
#

# In Openstack or Contrail High Availability setups.
# internal_vip          : Virtual IP of the openstack HA Nodes in the data/control(internal) nerwork,
#                         all the Openstack services behind this VIP are accessed using this VIP.
# external_vip          : Virtual IP of the Openstack HA Nodes in the management(external) nerwork,
#                         Openstack dashboard and novncproxy  services behind this VIP are accessed using this VIP.
# contrail_internal_vip : Virtual IP of the Contrail HA Nodes in the data/control(internal) nerwork,
#                         all the Contrail services behind this VIP is accessed using this VIP.
# contrail_external_vip : Virtual IP of the Contrail HA Nodes in the management(external) nerwork,
#                         Contrail introspects are are accessed using this VIP.
# nfs_server            : NFS server to be used to store the glance images.
# nfs_glance_path       : NFS server image path, which will be mounted on the Openstack Nodes and
#                         the glance images will be placed/accesed in/from this location.
#env.ha = {
#    'internal_vip'   : '1.1.1.100',               #Internal Virtual IP of the openstack HA Nodes.
#    'external_vip'   : '2.2.2.200',               #External Virtual IP of the openstack HA Nodes.
#    'contrail_internal_vip'   : '1.1.1.10',       #Internal Virtual IP of the contrail HA Nodes.
#    'contrail_external_vip'   : '2.2.2.20',       #External Virtual IP of the contrail HA Nodes.
#    'nfs_server'      : '3.3.3.3',                #IP address of the NFS Server which will be mounted to /var/lib/glance/images of openstack Node, Defaults to env.roledefs['compute'][0]
#    'nfs_glance_path' : '/var/tmp/images/',       #NFS Server path to save images, Defaults to /var/tmp/glance-images/
#}

# In environments where openstack services are deployed independently 
# from contrail, you can use the below options 
# service_token : Common service token for for all services like nova,
#                 neutron, glance, cinder etc
# amqp_host     : IP of AMQP Server to be used in openstack
# manage_amqp   : Default = 'no', if set to 'yes' provision's amqp in openstack nodes and
#                 openstack services uses the amqp in openstack nodes instead of config nodes.
#                 amqp_host is neglected if manage_amqp is set
#
#env.openstack = {
#    'service_token' : '33c57636fbc2c5552fd2', #Common service token for for all openstack services
#    'amqp_host' : '10.204.217.19',            #IP of AMQP Server to be used in openstack
#    'manage_amqp' : 'yes',                    #Default no, Manage seperate AMQP for openstack services in openstack nodes.
#}

# Link-Local Metadata Service
# By default fab scripts will retrieve metadata secret from openstack node.
# To override, Specify Metadata proxy secret from Openstack node
#neutron_metadata_proxy_shared_secret = <secret>

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

#To enable LBaaS feature
# Default Value: False
#env.enable_lbaas = True

#OPTIONAL REMOTE SYSLOG CONFIGURATION
#===================================
#For R1.10 this needs to be specified to enable rsyslog.
#For Later releases this would be enabled as part of provisioning,
#with following default values.
#
#port = 19876
#protocol = tcp
#collector = dynamic i.e. rsyslog clients will connect to servers in a round
#                         robin fasion. For static collector all clients will
#                         connect to a single collector. static - is a test
#                         only option.
#status = enable
#
#env.rsyslog_params = {'port':19876, 'proto':'tcp', 'collector':'dynamic', 'status':'enable'}

#OPTIONAL Virtual gateway CONFIGURATION
#=======================================

#Section vgw is only relevant when you want to use virtual gateway feature. 
#You can use one of your compute node as  gateway .

#Definition for the Key used
#-------------------------------------
#vn: Virtual Network fully qualified name. This particular VN will be used by VGW.
#ipam-subnets: Subnets used by vn. It can be single or multiple
#gateway-routes: If any route is present then only those routes will be published
#by VGW or Default route (0.0.0.0) will be published


#env.vgw = {host4: {'vgw1':{'vn':'default-domain:admin:public:public', 'ipam-subnets': ['10.204.220.128/29', '10.204.220.136/29', 'gateway-routes': ['8.8.8.0/24', '1.1.1.0/24']}]},
#                   'vgw2':{'vn':'default-domain:admin:public1:public1', 'ipam-subnets': ['10.204.220.144/29']}},
#           host5: {'vgw2':{'vn':'default-domain:admin:public1:public1', 'ipam-subnets': ['10.204.220.144/29']}}
#          }

#OPTIONAL optional tor agent and tsn CONFIGURATION
#==================================================
#Section tor agent is only relevant when you want to use Tor Agent feature. 
#You can use one of your compute node as  Tor Agent . Same or diffrent compute
#node should be enable as tsn

#Definition for the Key used
#-------------------------------------
# tor_ip: IP of the tor switch
# tor_id: Unique Id of the tor switch to identify. Typicaly a numeric value.
# tor_ovs_port: Port number to be used by ovs
# tor_ovs_protocol: Connection protocol to be used by ovs. Currently only TCP
# tor_tsn_ip: TSN node ip
# tor_tsn_name: Name of the TSN node
# tor_name: Name of the tor switch 
# tor_tunnel_ip: Data plane IP for the tor switch
# tor_vendor_name: Vendor type for TOR switch
# tor_http_server_port: HTTP server port. Same will be used by tor agent
# introspect
#env.tor_agent = {host10:[{
#                    'tor_ip':'10.204.217.39', IP of the tor switch
#                    'tor_id':'1',
#                    'tor_type':'ovs',
#                    'tor_ovs_port':'9999',
#                    'tor_ovs_protocol':'tcp',
#                    'tor_tsn_ip':'10.204.221.35',
#                    'tor_tsn_name':'nodec45',
#                    'tor_name':'bng-contrail-qfx51-2',
#                    'tor_tunnel_ip':'34.34.34.34',
#                    'tor_vendor_name':'Juniper'
#                    'tor_http_server_port': '9010',
#                       }]
#                }
#######################################
#vcenter provisioning
#server is the vcenter server ip
#port is the port on which vcenter is listening for connection
#username is the vcenter username credentials
#password is the vcenter password credentials
#auth is the autentication type used to talk to vcenter, http or https
#datacenter is the datacenter name we are operating on
#cluster is the clustername we are operating on
#dvswitch section contains distributed switch related para,s
#       dv_switch_name 
#dvportgroup section contains the distributed port group info
#       dv_portgroupname and the number of ports the group has
######################################
#env.vcenter = {
#        'server':'127.0.0.1',
#        'port': '443',
#        'username': 'administrator@vsphere.local',
#        'password': 'Contrail123!',
#        'auth': 'https',
#        'datacenter': 'kd_dc',
#        'cluster': 'kd_cluster',
#        'dv_switch': { 'dv_switch_name': 'kd_dvswitch',
#                     },
#        'dv_port_group': { 'dv_portgroup_name': 'kd_dvportgroup',
#                           'number_of_ports': '3',
#                     },
#}

####################################################################################
# The compute vm provisioning on ESXI host
# This section is used to copy a vmdk on to the ESXI box and bring it up 
# the contrailVM which comes up will be setup as a compute node with only
# vrouter running on it. Each host has an associated esxi to it. 
#
# esxi_host information:
#    ip: the esxi ip on which the contrailvm(host/compute) runs
#    username: username used to login to esxi
#    password: password for esxi
#    fabric_vswitch: the name of the underlay vswitch that runs on esxi 
#                    optional, defaults to 'vswitch0'
#    fabric_port_group: the name of the underlay port group for esxi
#                       optional, defaults to contrail-fab-pg'
#    uplinck_nic: the nic used for underlay
#                 optional, defaults to None
#    data_store: the datastore on esxi where the vmdk is copied to
#    contrail_vm information:
#        mac: the virtual mac address for the contrail vm
#        host: the contrail_vm ip in the form of 'user@contrailvm_ip'
#        vmdk: the absolute path of the contrail-vmdk used to spawn vm
#              optional, if vmdk_download_path is specified
#        vmdk_download_path: download path of the contrail-vmdk.vmdk used to spawn vm  
#                            optional, if vmdk is specified
#        deb: absolute path of the contrail package to be installed on contrailvm
#             optional, if contrail package is specified in command line
#        ntp_server: ntp server ip for the contrail vm 
######################################################################################
#esxi_hosts = {
#       'esxi': {
#             'ip': '1.1.1.1',
#             'username': 'root',
#             'password': 'c0ntrail123',
#             'datastore': "/vmfs/volumes/ds1",
#             'contrail_vm': {
#                   'mac': "00:50:56:05:ba:ba",
#                   'host': "root@2.2.2.2",
#                   'vmdk_download_path': "http://10.84.5.100/vmware/vmdk/ContrailVM-disk1.vmdk",
#                   'ntp_server': "10.84.9.17",
#             }
#       }
#}

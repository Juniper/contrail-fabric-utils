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
    #'rally': [host11], # Optional, to enable/setup rally, it can be a seprate node from contrail cluster
    # 'vgw': [host4, host5], # Optional, Only to enable VGW. Only compute can support vgw
    # 'tsn': [host1], # Optional, Only to enable TSN. Only compute can support TSN
    # 'toragent': [host1], Optional, Only to enable Tor Agent. Only compute can
    # support Tor Agent
    #   'backup':[backup_node],  # only if the backup_node is defined
}

#Hostnames
# Deprecated 'all' key from release 3.0; Consider specifying the hostname for each host seperately as below
#env.hostnames = {
#    'all': ['a0s1', 'a0s2', 'a0s3','a0s4', 'a0s5', 'a0s6', 'a0s7', 'a0s8', 'a0s9', 'a0s10','backup_node']
#}
env.hostnames = {
    host1: 'a0s1',
    host2: 'a0s2',
    host3: 'a0s3',
    host4: 'a0s4',
    host5: 'a0s5',
    host6: 'a0s6',
    host7: 'a0s7',
    host8: 'a0s8',
    host9: 'a0s9',
    host10: 'a0s10',
}

#Openstack admin password
env.openstack_admin_password = 'secret123'

# Passwords of each host
# for passwordless login's no need to set env.passwords,
# instead populate env.key_filename in testbed.py with public key.
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

# SSH Public key file path for passwordless logins
# if env.passwords is not specified.
#env.key_filename = '/root/.ssh/id_rsa.pub'

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

#Following section contains the SRIO configuration. For a given host, it
#is a list {interface, number of Virtual functions on the interface, and
#the allowed provider networks on that interface
#env.sriov = {
#     host2 :[ {'interface' : 'eth0', 'VF' : 7, 'physnets' : ['physnet1', 'physnet2']}, { 'interface' : 'eth1', 'VF' : 5, 'physnets' : ['physnet3', 'physnet4']}]
#}

#env.orchestrator = 'openstack' #other values are 'vcenter', 'none' default:openstack

#ntp server the servers should point to
#env.ntp_server = 'ntp.juniper.net'

# OPTIONAL COMPUTE HYPERVISOR CHOICE:
#======================================
# Compute Hypervisor
#env.hypervisor = {
#    host5: 'docker',
#    host6: 'libvirt',
#    host10: 'docker',
#}
#  Specify the hypervisor to be provisioned in the compute node.(Default=libvirt)


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

#following parameter allows to specify minimum amount of disk space in the analytics
#database partition, if configured amount of space is not present, it will fail provisioning
#minimum_diskGB = 256

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

#OPTIONAL Storage data network
#==================================================================================
#storage_data = {
#    host1 : { 'ip': '192.168.11.1/24', 'gw' : '192.168.11.254', 'device':'eth3' },
#    host2 : { 'ip': '192.168.11.2/24', 'gw' : '192.168.11.254', 'device':'eth3' },
#    host3 : { 'ip': '192.168.11.3/24', 'gw' : '192.168.11.254', 'device':'eth4' },
#    host4 : { 'ip': '192.168.11.4/24', 'gw' : '192.168.11.254', 'device':'eth3' },
#    host5 : { 'ip': '192.168.11.5/24', 'gw' : '192.168.11.254', 'device':'bond0' },
#    host6 : { 'ip': '192.168.11.6/24', 'gw' : '192.168.11.254', 'device':'eth3' },
#    host7 : { 'ip': '192.168.11.7/24', 'gw' : '192.168.11.254', 'device':'eth4' },
#    host8 : { 'ip': '192.168.11.8/24', 'gw' : '192.168.11.254', 'device':'eth3' },
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
#    host7 : { 'nfs' : ['10.10.10.10:/nfs', '11.11.11.11:/nfs']},
#}
#Set Storage replica
#storage_replica_size = 3

#Base Openstack live migration configuration.
#live_migration = True
#Fix uid/gid for nova/libvirt-qemu so the ids are same across all nodes.
#nova_uid_fix = True

#Following are NFS based live migration configuration
#Enable this for External NFS server based live migration
#ext_nfs_livem = True
#ext_nfs_livem_mount = '11.1.0.1:/nfsvol'

#Enable this for Ceph based NFS VM server based live migration
#ceph_nfs_livem = True
#ceph_nfs_livem_subnet = '192.168.10.253/24'
#ceph_nfs_livem_image = '/ubuntu/livemnfs.qcow2'
#ceph_nfs_livem_host = host4

#To disable installing contrail interface rename package
#env.interface_rename = False


#Path where the CA certificate file is stored on the node where fab is run.
#Fab copies the file to node where TOR agent is run.
#This is optional and is required only when tor_ovs_protocol is pssl.
#The certificates on the TOR are based on this CA cert.
#env.ca_cert_file = '/root/file.pem'

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
#    'keystone_ip'     : 'x.y.z.a',
#    'auth_protocol'   : 'http',                  #Default is http
#    'auth_port'       : '35357',                 #Default is 35357
#    'admin_token'     : '33c57636fbc2c5552fd2',  #admin_token in keystone.conf
#    'admin_user'      : 'admin',                 #Default is admin
#    'admin_password'  : 'contrail123',           #Default is contrail123
#    'nova_password'   : 'contrail123',           #Default is the password set in admin_password
#    'neutron_password': 'contrail123',           #Default is the password set in admin_password
#    'service_tenant'  : 'service',               #Default is service
#    'admin_tenant'    : 'admin',                 #Default is admin
#    'region_name'     : 'RegionOne',             #Default is RegionOne
#    'insecure'        : 'True',                  #Default = False
#    'manage_neutron'  : 'no',                    #Default = 'yes' , Does configure neutron user/role in keystone required.
#}
#

#env.nova = {
#    'cpu_mode': 'host-passthrough', # Possible options: none, host-passthrough, host-model, and custom
#                                    # if cpu_mode is 'custom' specify cpu_model option too
#    'cpu_model': 'Nehalem',         # relevant only if cpu_mode is 'custom'
#}

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
# internal_virtual_router_id : Virtual router ID for the Openstack HA nodes in control/data(internal) network.
# external_virtual_router_id : Virtual router ID for the Openstack HA nodes in management(external) network.
# contrail_internal_virtual_router_id : Virtual router ID for the Contrail HA nodes in control/data(internal) network.
# contrail_external_virtual_router_id : Virtual router ID for the Contrail HA nodes in  management(external) network.
#env.ha = {
#    'internal_vip'   : '1.1.1.100',               #Internal Virtual IP of the openstack HA Nodes.
#    'external_vip'   : '2.2.2.200',               #External Virtual IP of the openstack HA Nodes.
#    'contrail_internal_vip'   : '1.1.1.10',       #Internal Virtual IP of the contrail HA Nodes.
#    'contrail_external_vip'   : '2.2.2.20',       #External Virtual IP of the contrail HA Nodes.
#    'nfs_server'      : '3.3.3.3',                #IP address of the NFS Server which will be mounted to /var/lib/glance/images of openstack Node, Defaults to env.roledefs['compute'][0]
#    'nfs_glance_path' : '/var/tmp/images/',       #NFS Server path to save images, Defaults to /var/tmp/glance-images/
#    'internal_virtual_router_id' :  180,                   #Default = 100
#    'external_virtual_router_id' :  190,          #Default = 100
#    'contrail_internal_virtual_router_id' :  200, #Default = 100
#    'contrail_external_virtual_router_id' :  210, #Default = 100

#}

# In environments where openstack services are deployed independently
# from contrail, you can use the below options
# service_token : Common service token for for all services like nova,
#                 neutron, glance, cinder etc
# amqp_host     : IP of AMQP Server to be used in openstack
# manage_amqp   : Default = 'no', if set to 'yes' provision's amqp in openstack nodes and
#                 openstack services uses the amqp in openstack nodes instead of config nodes.
#                 amqp_host is neglected if manage_amqp is set
# service_dbpass: Default = 'c0ntrail123'; DB password of all openstack service users
#
#env.openstack = {
#    'service_token' : '33c57636fbc2c5552fd2', #Common service token for for all openstack services
#    'amqp_host' : '10.204.217.19',            #IP of AMQP Server to be used in openstack
#    'manage_amqp' : 'yes',                    #Default no, Manage seperate AMQP for openstack services in openstack nodes.
#    'osapi_compute_workers' : 40,             #Default 40, For low memory system reduce the osapi compute workers thread.
#    'conductor_workers' : 40,                 #Default 40, For low memory system reduce the conductor workers thread.
#    'service_dbpass' : 'c0ntrail123',         #DB password of all openstack service users
#}

#Config node related config knobs
#amqp_hosts : List of customer deployed AMQP servers to be used by config services.
#amqp_port : Port of the customer deployed AMQP servers.
#env.cfgm = {
#    'amqp_hosts' : ['10.10.10.1', '10.10.10.2']
#    'amqp_port' : '5672'
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

# Ceilometer enable/disable installation and provisioning
# Default Value: False
#enable_ceilometer = True

# Ceilometer polling interval for meters in seconds
# Default Value: 600
#ceilometer_polling_interval = 600

# Ceilometer data TTL in seconds
# Default Value: 7200
#ceilometer_ttl = 7200

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
# tor_agent_id: Unique Id of the tor switch to identify. Typicaly a numeric value.
# tor_agent_name: Unique name for TOR Agent. This is an optional field. If this is
#                 not specified, name used will be <hostname>-<tor_id>
# tor_type: Always ovs
# tor_ovs_port: Port number to be used by ovs. If any redundant TOR Agent is
#               specified for this tor-agent, it should have the same 'tor_ovs_port'
# tor_ovs_protocol: Connection protocol between TOR Agent and TOR (tcp / pssl)
# tor_tsn_ip: TSN node ip
# tor_tsn_name: Name of the TSN node
# tor_name: Name of the tor switch. If any redundant TOR Agent is specified for
#           this tor-agent, it should have the same 'tor_name'
# tor_tunnel_ip: Data plane IP for the tor switch
# tor_vendor_name: Vendor type for TOR switch
# tor_product_name: Product name of TOR switch. This is an optional field.
# tor_agent_http_server_port: HTTP server port. Same will be used by tor agent for introspect
# tor_agent_ovs_ka: Tor Agent OVSDB keepalive timer in milli seconds
#
#env.tor_agent = {host10:[{
#                    'tor_ip':'10.204.217.39',
#                    'tor_agent_id':'1',
#                    'tor_agent_name':'nodexx-1',
#                    'tor_type':'ovs',
#                    'tor_ovs_port':'9999',
#                    'tor_ovs_protocol':'tcp',
#                    'tor_tsn_ip':'10.204.221.35',
#                    'tor_tsn_name':'nodec45',
#                    'tor_name':'bng-contrail-qfx51-2',
#                    'tor_tunnel_ip':'34.34.34.34',
#                    'tor_vendor_name':'Juniper',
#                    'tor_product_name':'QFX5100',
#                    'tor_agent_http_server_port': '9010',
#                    'tor_agent_ovs_ka': '10000',
#                       }]
#                }

####################################################################################
#vcenter provisioning
#server is the vcenter server ip
#port is the port on which vcenter is listening for connection
#username is the vcenter username credentials
#password is the vcenter password credentials
#auth is the autentication type used to talk to vcenter, http or https
#datacenter is the datacenter name we are operating on
#cluster is the clustername we are operating on
#vcenter_compute is the nova-compute node for this vcenter cluster,
#         applicable only for vcenter-as-compute mode
#dv_switch_fab section contains distributed switch related params for fab network
#       dv_switch_name
#dv_port_group_fab section contains distributed port group params for fab network
#       dv_portgroup_name and the number of ports the group has
#dv_switch_sr_iov section contains distributed switch related params for sr-iov based fab network
#       dv_switch_name
#dv_port_group_sr_iov section contains distributed port group params for sr-iov based fab network
#       dv_portgroup_name and the number of ports the group has
#dvswitch section contains distributed switch related params for overlay network
#       dv_switch_name
#dvportgroup section contains distributed port group info for overlay network
#       dv_portgroup_name and the number of ports the group has
####################################################################################
#env.vcenter_servers = {
#        'vcenter1': {
#                  'server':'127.0.0.1',
#                  'port': '443',
#                  'username': 'administrator@vsphere.local',
#                  'password': 'Contrail123!',
#                  'auth': 'https',
#                  'datacenter': 'kd_dc',
#                  'cluster': ['kd_cluster_1','kd_cluster_2'],
#                  'vcenter_compute' : '1.1.1.2',
#                  'dv_switch_fab': {'dv_switch_name': 'dvs-lag'},
#                  'dv_port_group_fab': {
#                          'dv_portgroup_name': 'fab-pg',
#                          'number_of_ports': '3',
#                  },
#                  'dv_switch_sr_iov': {'dv_switch_name': 'dvs-sr-iov'},
#                  'dv_port_group_sr_iov': {
#                          'dv_portgroup_name': 'sr-iov-pg',
#                          'number_of_ports': '2',
#                  },
#                 'dv_switch': { 'dv_switch_name': 'kd_dvswitch'},
#                 'dv_port_group': {
#                          'dv_portgroup_name': 'kd_dvportgroup',
#                          'number_of_ports': '3',
#                 },
#        },
#}
#
######################################################################################
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
#    uplink_nic: the nic used for underlay
#                 optional, defaults to None
#    data_store: the datastore on esxi where the vmdk is copied to
#    vcenter_server: the vcenter_server name which manages this esxi
#    cluster: name of the cluster to which this esxi is added
#    contrail_vm information:
#        mac: the virtual mac address for the contrail vm
#        host: the contrail_vm ip in the form of 'user@contrailvm_ip'
#        mode: the mode is 'openstack' or 'vcenter'
#               optional, defaults to env.orchestrator value
#        pci_devices: pci_devices information
#            nic: pci_id of the pass-through interfaces
#        sr_iov_nics: virtual functions enabled physical interface's name
#        vmdk: the absolute path of the contrail-vmdk used to spawn vm
#              optional, if vmdk_download_path is specified
#        vmdk_download_path: download path of the contrail-vmdk.vmdk used to spawn vm
#                            optional, if vmdk is specified
######################################################################################
#esxi_hosts = {
#       'esxi': {
#             'ip': '10.1.1.1',
#             'username': 'root',
#             'password': 'c0ntrail123',
#             'datastore': "/vmfs/volumes/ds1", 
#             'vcenter_server': "vcenter1",
#             'cluster': "kd_cluster_1",
#             'contrail_vm': {
#                   'mac': "00:50:56:05:ba:ba",
#                   'host': "root@1.1.1.4",
#                   'mode': "vcenter",
#                   'pci_devices': {
#                        nic: ["04:00.0", "04:00.1"],
#                    },
#                   'sr_iov_nics': ["vmnic0"],
#                   'vmdk_download_path': "http://10.84.5.100/vmware/vmdk/ContrailVM-disk1.vmdk",
#             }
#       }
#}
######################################################################################

# OPTIONAL DPDK CONFIGURATION
# ===========================
# If some compute nodes should use DPDK vRouter version it has to be put in
# env.dpdk dictionary. The format is:
# env.dpdk = {
#     host1: { 'huge_pages' : '50', 'coremask' : '0xf' },
#     host2: { 'huge_pages' : '50', 'coremask' : '0,3-7' },
# }
# huge_pages - Specify what percentage of host memory should be reserved
#              for access with huge pages
# coremask   - Specify CPU affinity mask to run vRouter with. Supported formats:
#              hexadecimal, comma-sepparated list of CPUs, dash-separated range
#              of CPUs.
# OPTIONAL vrouter limit parameter
# ==================================
#env.vrouter_module_params = {
#     host4:{'mpls_labels':'131072', 'nexthops':'131072', 'vrfs':'65536', 'macs':'262144'},
#     host5:{'mpls_labels':'131072', 'nexthops':'131072', 'vrfs':'65536', 'macs':'262144'}
#}
# OPTIONAL md5 key enabling
# There are 2 ways of enabling BGP md5 key on node apart from the webui.
# 1. Before provisioning the node, include an env dict in testbed.py as shown below specifying the desired key value #    on the node. The key should be of type "string" only.
# 2. If md5 is not included in testbed.py and the node is already provisioned, you can run the
#    contrail-controller/src/config/utils/provision_control.py script with a newly added argument for md5
# The below env dict is for first method specified, where you include a dict in testbed.py as shown below:
#  env.md5 = {
#     host1: 'juniper',
#     host2: 'juniper',
#     host3: 'juniper',
#  }
# 'juniper' is the md5 key that will be configured on the nodes.
############################################################################################


# OPTIONAL RALLY CONFIGURATION
# =======================================
# Rally is installed from github source, with default to be github.com/openstack/rally.git.
# There are two params can be added here to control any different repo to be used,
# rally_git_url - the git url from which source can be cloned (git or https url can be provided)
# rally_git_branch - branch name to be used, default to master.
#        Since we customized couple of rally plugin code, we should provide these parameters with appropriate git repo
# rally_task_args - rally task arguments  - a hash of arguments taken by scenarios.yaml jinja2 template
##
#rally_git_url = 'https://github.com/hkumarmk/rally'
#rally_git_branch = 'network_plus'
#rally_task_args = {'cxt_tenants': 1, 'cxt_users_per_tenant': 4, 'cxt_network': True, 'base_network_load_objects': 20000, 'load_type': 'constant', 'times': 2}

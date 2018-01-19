from fabric.api import env

#Management ip addresses of hosts in the cluster
host1 = 'root@<Mgmt IP Address>'


#External routers if any
#for eg. 
#ext_routers = [('mx1', '1.1.1.253')]
ext_routers = []

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'root@<Mgmt IP Address>'


#Role definition of the hosts.
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
    'storage-master': [host1],
    'storage-compute': [host1],
    #'oldcfgm': [host2] old cfgm for ISSU
    #'oldcontrol':[host2] old control for ISSU
    #'olddatabase':[host2] old database for ISSU
    #'oldcollector':[host2] old collector for ISSU
    #'oldwebui':[host2] old webui for ISSU
    #'oldbuild':[host2] old build for ISSU
    # 'rally': [host1], # Optional, to enable/setup rally, it can be a seprate node from contrail cluster
    # 'vgw': [host1], # Optional, Only to enable VGW. Only compute can support vgw
    # 'tsn': [host1], # Optional, Only to enable TSN. Only compute can support TSN
    # 'toragent': [host1], Optional, Only to enable Tor Agent. Only compute can
    # support Tor Agent
 #   'backup':[backup_node],  # only if the backup_node is defined
}

#Openstack admin password
env.openstack_admin_password = '<Password value>'

#Hostnames
# Deprecated 'all' key from release 3.0; Consider specifying the hostname for each host seperately as below
#env.hostnames = {
#    'all': ['a0s1']
#}
env.hostnames = {
    host1: 'a0s1',
}

# Passwords of each host
# for passwordless login's no need to set env.passwords,
# instead populate env.key_filename in testbed.py with public key.
env.passwords = {
    host1: '<Password value>',
  #  backup_node: '<Password value>',
    host_build: '<Password value>',
}

# SSH Public key file path for passwordless logins
# if env.passwords is not specified.
#env.key_filename = '/root/.ssh/id_rsa.pub'

#For reimage purpose
env.ostypes = {
    host1:'centos',
}
#env.orchestrator = 'openstack' #other values are 'vcenter', 'none' default:openstack

#ntp server the servers should point to
#env.ntp_server = 'ntp.juniper.net'

# OPTIONAL COMPUTE HYPERVISOR CHOICE:
#======================================
# Compute Hypervisor
#env.hypervisor = {
#    host1: 'docker',
#}
#  Specify the hypervisor to be provisioned in the compute node.(Default=libvirt)

# INFORMATION FOR DB BACKUP/RESTORE ..
#=======================================================
#Optional,Backup Host configuration if it is not available then it will put in localhost
#backup_node = 'root@2.2.2.2'

# Optional, Local/Remote location of backup_data path 
# if it is not passed it will use default path 
#backup_db_path= ['/home/','/root/']
#cassandra backup can be defined either "full" or "custom"  
#full -> take complete snapshot of cassandra DB 
#custom -> take snapshot except defined in skip_keyspace 
#cassandra_backup='custom'  [ MUST OPTION] 
#skip_keyspace=["ContrailAnalytics"]  IF cassandra_backup is selected as custom
#service token need to define to do  restore of  backup data
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
#analyticsdb_minimum_diskgb = 256
#configdb_minimum_diskgb = 20

#OPTIONAL BONDING CONFIGURATION
#==============================
#Inferface Bonding
#bond= {
#    host1 : { 'name': 'bond0', 'member': ['p2p0p0','p2p0p1','p2p0p2','p2p0p3'], 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4' },
#}

#OPTIONAL SEPARATION OF MANAGEMENT AND CONTROL + DATA and OPTIONAL VLAN INFORMATION
#==================================================================================
#control_data = {
#    host1 : { 'ip': 'x.x.x.1/24', 'gw' : 'x.x.x.254', 'device': 'bond0', 'vlan': '224' },
#}

#OPTIONAL STATIC ROUTE CONFIGURATION
#===================================
#static_route  = {
#    host1 : [{ 'ip': '1.1.1.0', 'netmask' : 'x.x.x.0', 'gw':'x.x.x.254', 'intf': 'bond0' },
#             { 'ip': '1.1.2.0', 'netmask' : 'x.x.x.0', 'gw':'x.x.x.254', 'intf': 'bond0' }],
#}

#storage compute disk config
#storage_node_config = {
#    host1 : { 'disks' : ['sdc', 'sdd'] },
#}

#live migration config
#live_migration = True


#To disable installing contrail interface rename package
#env.interface_rename = False

# In environments where openstack/keystone services are deployed independently
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
#  certfile # Specify local remote(openstack node) path to certificate file
            # If local path specifed, it will be copied to openstack node(/etc/keystone/ssl/certs/keystone.pem)
            # If remote path in openstack node specified, Keystone.conf will point to the specified location
#  keyfile # Specify local remote(openstack node) path to key file
            # If local path specifed, it will be copied to openstack node(/etc/keystone/ssl/private/keystone_key.pem)
            # If remote path in openstack node specified, Keystone.conf will point to the specified location
#  cafile # Specify local remote(openstack node) path to ca certificate file
            # If local path specifed, it will be copied to openstack node(/etc/keystone/ssl/certs/keystone_ca.pem)
            # If remote path in openstack node specified, Keystone.conf will point to the specified location
#
#env.keystone = {
#    'keystone_ip'     : 'x.y.z.a',
#    'auth_protocol'   : 'http',                  #Default is http
#    'auth_port'       : '35357',                 #Default is 35357
#    'admin_token'     : '33c57636fbc2c5552fd2',  #admin_token in keystone.conf
#    'admin_user'      : 'admin',                 #Default is admin
#    'admin_password'  : '<Password value>',      
#    'nova_password'   : '<Nova Password value>', #Default is the password set in admin_password
#    'neutron_password': '<Neutron Password value>',  #Default is the password set in admin_password
#    'service_tenant'  : 'service',               #Default is service
#    'admin_tenant'    : 'admin',                 #Default is admin
#    'region_name'     : 'RegionOne',             #Default is RegionOne
#    'insecure'        : 'True',                  #Default = False
#    'certfile'        : '/root/keystone.pem',    #Default /etc/keystone/ssl/certs/keystone.pem
#    'keyfile'         : '/root/keystone_key.pem',#Default /etc/keystone/ssl/private/keystone_key.pem
#    'cafile'          : '/root/keystone_ca.pem', #Default /etc/keystone/ssl/certs/keystone_ca.pem
#    'manage_neutron'  : 'no',                    #Default = 'yes' , Does configure neutron user/role in keystone required.
#}
#

#env.nova = {
#    'cpu_mode': 'host-passthrough', # Possible options: none, host-passthrough, host-model, and custom
#                                    # if cpu_mode is 'custom' specify cpu_model option too
#    'cpu_model': 'Nehalem',         # relevant only if cpu_mode is 'custom'
#}

# Openstack specific configuration options
# service_token : Common service token for for all services like nova,
#                 neutron, glance, cinder etc
# amqp_host     : IP of AMQP Server to be used in openstack
# manage_amqp   : Default = 'no', if set to 'yes' provision's amqp in openstack nodes and
#                 openstack services uses the amqp in openstack nodes instead of config nodes.
#                 amqp_host is neglected if manage_amqp is set
# service_dbpass: Default = '<DB Password>'; DB password of all openstack service users
#
#env.openstack = {
#    'service_token' : '33c57636fbc2c5552fd2', #Common service token for for all openstack services
#    'amqp_host' : '1.1.1.19',            #IP of AMQP Server to be used in openstack
#    'manage_amqp' : 'yes',                    #Default no, Manage seperate AMQP for openstack services in openstack nodes.
#    'osapi_compute_workers' : 40,             #Default 40, For low memory system reduce the osapi compute workers thread.
#    'conductor_workers' : 40,                 #Default 40, For low memory system reduce the conductor workers thread.
#    'service_dbpass' : '<DB Password>',         #DB password of all openstack service users
#}

#Config node related config knobs
# amqp_hosts : List of customer deployed AMQP servers to be used by config services.
# amqp_port : Port of the customer deployed AMQP servers.
# haproxy_token : Password of the haproxy user(haproxy) running in cfgm nodes,
#                 Default is auto generated(/etc/contrail/haproxy.token)
# manage_db : Manage seperate cassandra DB for config objects in config(cfgm) node.
#              Defaults to 'yes'.
# keyfile  : Specify local remote(cfgm node) path to key file
#            If local path specifed, it will be copied to cfgm node(/etc/contrail/ssl/private/apiserver_key.pem)
#            If remote path in cfgm node specified, contrail-api.conf will point to the specified location
# cafile   : Specify local remote(cfgm node) path to key file
#            If local path specifed, it will be copied to cfgm node(/etc/contrail/ssl/certs/apiserver_ca.pem)
#            If remote path in cfgm node specified, contrail-api.conf will point to the specified location
# certfile : Specify local remote(cfgm node) path to certificate file
#            If local path specifed, it will be copied to cfgm node(/etc/contrail/ssl/certs/apiserver.pem)
#            If remote path in cfgm node specified, contrail-api.conf will point to the specified location
#env.cfgm = {
#    'amqp_hosts' : ['1.1.10.1', '1.1.10.2'],
#    'amqp_port' : '5672',
#    'haproxy_token' : '<Password value>',
#    'manage_db' : 'no',
#    'auth_protocol'   : 'http',                  #Default is http
#    'insecure'        : 'True',                   #Default is False
#    'certfile'        : '/root/apiserver.pem',    #Default is '/etc/contrail/ssl/certs/apiserver.pem'
#    'keyfile'         : '/root/apiserver_key.pem',#Default is '/etc/contrail/ssl/private/apiserver_key.pem'
#    'cafile'          : '/root/apiserver_ca.pem', #Default is '/etc/contrail/ssl/certs/apiserver_ca.pem'
#}

# Neutron specific configuration 
#env.neutron = {
#   'protocol': 'http', # Default is http
#}

#To enable multi-tenancy feature
#multi_tenancy = True

# Name of cloud-admin role
# (admin by default)
#cloud_admin_role = 'admin'

# Set analytics aaa_mode. Possible options are no-auth, cloud-admin.
# (cloud-admin by default)
#analytics_aaa_mode = 'cloud-admin'

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

# Gateway Mode to support Remote Instances can be server/vcpe
# Set the computes which will act as gateway
#env.compute_as_gateway_mode = {
#   host1 : 'server',
#}

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

#env.vgw = {host1: {'vgw1':{'vn':'default-domain:admin:public:public', 'ipam-subnets': ['1.1.1.100/29', '1.1.1.150/29', 'gateway-routes': ['8.8.8.0/24', '1.1.1.0/24']}]},
#                   'vgw2':{'vn':'default-domain:admin:public1:public1', 'ipam-subnets': ['1.1.1.160/29']}
#          }

#Definition for the Key used
#--------------------------------------
# For Qos hardware queues (nic queues) are mapped to logical queues in agent.
# hardware_q_id: Identifier for the hardwarwe queue.
# logical_queue: Defines the logical queues each hardware queue is mapped to.
# default: When set to True defines the default hardware queue for Qos.
# Defining a default hardware queue:
#     1) Just set the queue as default, without any logical_queue mapping:
#         {'hardware_q_id': '1', 'default': 'True'}
#     2) Set the hardware queue as default with logical queue mapping:
#         {'hardware_q_id': '6', 'logical_queue':['17-20'], 'default': 'True'}

#env.qos = {host1: [ {'hardware_q_id': '3', 'logical_queue':['1', '6-10', '12-15']},
#                    {'hardware_q_id': '5', 'logical_queue':['2']},
#                    {'hardware_q_id': '8', 'logical_queue':['3-5']},
#                    {'hardware_q_id': '1', 'logical_queue':['17-20'], 'default': 'True'}],
#          }

#Definition for the Key used for qos priority group
#--------------------------------------------------------------------
# priority_id: Priority group for qos.
# scheduling: Defines the scheduling algorithm used for priority group, strict or roundrobin (rr).
# bandwidth: Total hardware queue bandwidth used by priority group.
# Bandwidth cannot be specified if strict scheduling is used for priority group set it as 0.
#env.qos_niantic = {host1:[
#                     { 'priority_id': '1', 'scheduling': 'strict', 'bandwidth': '0'},
#                     { 'priority_id': '2', 'scheduling': 'rr', 'bandwidth': '20'},
#                     { 'priority_id': '3', 'scheduling': 'rr', 'bandwidth': '10'}],
#                  }

#OPTIONAL optional tor agent and tsn CONFIGURATION
#==================================================
#Section tor agent is only relevant when you want to use Tor Agent feature.
#You can use one of your compute node as  Tor Agent . Same or diffrent compute
#node should be enable as tsn

#Definition for the Key used
#-------------------------------------
# tor_ip: IP of the tor switch
# tor_agent_id: Unique Id of the tor switch to identify. Typicaly a numeric value.
# tor_agent_name: Unique name for TOR Agent. This is optional field. If this is
#                 not specified name used will be <hostname>-<tor_agent_id>
# tor_ovs_port: Port number to be used by ovs
# tor_ovs_protocol: Connection protocol to be used by ovs. Currently only TCP
# tor_tsn_ip: TSN node ip
# tor_agent_ovs_ka: Tor Agent OVSDB keepalive timer in milli seconds
#env.tor_agent =
#{host3:[{'tor_ip':'1.1.1.39','tor_agent_id':'1','tor_agent_name':'nodexx-1', 'tor_ovs_port':'9999','tor_ovs_protocol':'tcp','tor_tsn_ip':'1.1.1.35', 'tor_agent_ovs_ka':'10000'}]}

# OPTIONAL DPDK CONFIGURATION
# ===========================
# If some compute nodes should use DPDK vRouter version it has to be put in
# env.dpdk dictionary. The format is:
# env.dpdk = {
#     host1: { 'huge_pages' : '50', 'coremask' : '0xf', 'uio_driver' : 'uio_pci_generic' },
#     host2: { 'huge_pages' : '50', 'coremask' : '0,3-7', 'uio_driver' : 'vfio-pci' },
# }
# huge_pages - Specify what percentage of host memory should be reserved
#              for access with huge pages
# coremask   - Specify CPU affinity mask to run vRouter with. Supported formats:
#              hexadecimal, comma-separated list of CPUs, dash-separated range
#              of CPUs.
# uio_driver - UIO driver to use for DPDK. The driver is one of:
#                * igb_uio - DPDK driver with legacy and MSI-X interrupts
#                  support (defualt)
#                * uio_pci_generic - Linux standard UIO driver with legacy
#                  interrupts support only (i.e. no VF support)
#                * vfio-pci - Linux standard UIO driver with MSI-X support.
#                  IOMMU must be configured in order to use the driver.
#
# OPTIONAL vrouter limit parameter
# ==================================
#env.vrouter_module_params = {
#     host1:{'flow_entries':'4000000', 'mpls_labels':'131072', 'nexthops':'131072','vrfs':'65536','macs':'262144'},
#}
# OPTIONAL md5 key enabling
# There are 2 ways of enabling BGP md5 key on node apart from the webui.
# 1. Before provisioning the node, include an env dict in testbed.py as shown below specifying the desired key value #    on the node. The key should be of type "string" only.
# 2. If md5 is not included in testbed.py and the node is already provisioned, you can run the
#    contrail-controller/src/config/utils/provision_control.py script with a newly added argument for md5.
# The below env dict is for first method specified, where you include a dict in testbed.py as shown below:
#  env.md5 = {
#     host1: 'juniper',
#  }
# 'juniper' is the md5 key that will be configured on the node.

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

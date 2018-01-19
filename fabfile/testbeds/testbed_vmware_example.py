from fabric.api import env

#Management ip addresses of hosts in the cluster
host1 = 'root@1.1.1.7'
#host2 = 'root@1.1.1.8'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '1.1.1.253')]
ext_routers = []

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'root@1.1.1.56'

#Role definition of the hosts.
env.roledefs = {
#    'all': [host1,host2],
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

#Openstack admin password
env.openstack_admin_password = '<Password value>'

env.ostypes = { 
    host1:'ubuntu'
}

#Hostnames
env.hostnames = {
#    'all': ['nodec22', 'nodeg17']
    'all': ['nodec22']
}

env.password = '<Password value>'
#Passwords of each host
env.passwords = {
    host1: '<Password value>',
#    host2: '<Password value>',


    host_build: '<Password value>',
}

compute_vm = {
    host1: { 'esxi': {'ip': '1.1.1.35',
                      'username': 'root',
                      'password': '<password value>',
                      'uplink_nic': 'vmnic2',
                      'vswitch' : 'vSwitch0',
                      'vm_port_group' : 'contrail-compute1-fab-pg',
                     },
             'vm_name' : 'Fedora-Compute-VM1',
             'vmdk' : 'Fedora-Compute-VM1-disk1.vmdk',
             'vswitch': 'vSwitch1',
             'port_group' : 'contrail-compute1-pg',
    },
}
            
             

#OPTIONAL BONDING CONFIGURATION
#==============================
#Inferface Bonding
#bond= {
#    host1 : { 'name': 'bond0', 'member': ['p2p0p0','p2p0p1','p2p0p2','p2p0p3'], 'mode':'balance-xor' },
#}

#OPTIONAL SEPARATION OF MANAGEMENT AND CONTROL + DATA
#====================================================
#Control Interface
#control = {
#    host1 : { 'ip': 'x.x.x.1/24', 'gw' : 'x.x.x.254', 'device':'eth0' },
#}

#Data Interface
#data = {
#    host1 : { 'ip': 'x.x.x.1/24', 'gw' : 'x.x.x.254', 'device':'bond0' },
#}

#To disable installing contrail interface rename package
#env.interface_rename = False

#To use existing service_token
#service_token = 'your_token'

#Specify keystone IP
#keystone_ip = '1.1.1.1'

#Specify Region Name
#region_name = 'RegionName'

#To enable multi-tenancy feature
#multi_tenancy = True

#To enable haproxy feature
#haproxy = True

#To Enable prallel execution of task in multiple nodes
#do_parallel = True
env.test_repo_dir='<Path to test repo dir>'
env.mail_from='<Email>'
env.mail_to='<Email>'
env.log_scenario='Single-Node Sanity'

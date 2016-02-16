from fabric.api import env

#Management ip addresses of hosts in the cluster
host1 = 'root@10.84.24.222'
controller = 'root@10.84.24.54'
#openstack = 'root@10.84.24.63'
#host2 = 'root@10.204.217.57'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '10.204.216.253')]
ext_routers = []

#Autonomous system number
router_asn = 64512

#Host from which the fab commands are triggered to install and provision
host_build = 'vjoshi@10.204.216.56'

#Role definition of the hosts.
env.roledefs = {
#    'all': [host1,host2],
    'all': [host1],
    'cfgm': [controller],
    'openstack': [controller],
    'control': [controller],
    'compute': [host1],
    'collector': [controller],
    'webui': [controller],
    'database': [controller],
    'build': [controller],
}

#Openstack admin password
env.openstack_admin_password = 'contrail123'

env.ostypes = { 
    host1:'ubuntu'
}

#Hostnames
env.hostnames = {
#    'all': ['nodec22', 'nodeg17']
    'all': ['nodec22']
}

env.password = 'c0ntrial123'
#Passwords of each host
env.passwords = {
    host1: 'c0ntrail123',
    controller: 'c0ntrail123',
#    host2: 'c0ntrail123',


    host_build: 'secret',
}
vcenter = {
	'server':'10.84.24.111',
	'username': 'admin',
	'password': 'Contrail123!',
	'datacenter': 'kiran_dc',
	'cluster': 'kiran_cluster',
	'dv_switch': { 'dv_switch_name': 'kiran_dvswitch',
			'nic': 'vmnic1',
		     },
	'dv_port_group': { 'dv_portgroup_name': 'kiran_portgroup',
			   'number_of_ports': '3',
		     },
}

        

compute_vm = {
    host1: { 'esxi': {'esx_ip': '10.84.24.61',
                      'esx_username': 'root',
                      'esx_password': 'c0ntrail123',
                      'esx_uplink_nic': 'vmnic0',
                      'esx_fab_vswitch' : 'vSwitch0',
                      'esx_fab_port_group' : 'contrail-fab-pg',
		      'esx_ssl_thumbprint' : "62:49:C2:D4:F7:3A:AF:0F:DE:01:FB:52:7C:36:03:B2:33:CC:DC:EE",
                     },
             'server_mac' : "00:50:56:00:BA:BA",
             'server_ip': "10.84.24.222",
             'esx_vm_name' : "ContrailVM",
             #'esx_datastore' : "/vmfs/volumes/b4s4-root/",
             'esx_datastore' : "/vmfs/volumes/datastore1/",
             #'esx_vmdk' : '/cs-shared/contrail_fcs_images/v1.10/ubuntu/havana/ContrailVM-disk1.vmdk',
             'esx_vmdk' : '/users/kirand/vmware_integ/ContrailVM-disk1.vmdk',
	     'vm' : "ContrailVM",
             'vmdk' : "ContrailVM-disk1",
             'vm_deb' : '/cs-shared/contrail_fcs_images/v1.10/ubuntu/havana/contrail-install-packages_1.10-34~havana_all.deb',
             'esx_vm_vswitch': 'vSwitch1',
             'esx_vm_port_group' : 'contrail-vm-pg',
             'server_id' : 'contrail-vm',
             'password' : 'c0ntrail123',
             'domain' : 'englab.juniper.net',
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
#    host1 : { 'ip': '192.168.10.1/24', 'gw' : '192.168.10.254', 'device':'eth0' },
#}

#Data Interface
#data = {
#    host1 : { 'ip': '192.161.10.1/24', 'gw' : '192.161.10.254', 'device':'bond0' },
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
env.test_repo_dir='/homes/vjoshi/node22-17/test'
env.mail_from='vjoshi@juniper.net'
env.mail_to='vjoshi@juniper.net'
env.log_scenario='Single-Node Sanity'

#env.optional_services = {
#    'collector': ['snmp-collector', 'topology'],
#    'cfgm'     : ['device-manager'],
#}

#Setting Esxi hypervisor as compute node is a three step process

#1) fab prov_esxi which provisions the Esxi with the required vswitches
#and port groups. Also spawns the ContailVM on the esx server.
#The esxi hypervisor information is provided in
#esxi_hosts stanza as mentioned in this testbed.py file

#2) After instantiating ContrailVM, the IP address need to be updated in
#this testbed.py file like any other compute node. And other fab commands
#like 'fab install_pkg_all, install_contrail, setup_all' need to be
#followed


from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.204.217.14'
# Below is the ContrailVM on the Esxi Hypervisor. If the IP address of
# ContrailVM is not known prior to provisioning of Esxi, any dummy value
# can be written for Esxi provisioning and later modified to correct
# IP address of ContrailVM after instantiating ContrailVM on Esxi. The
# dummy value has to be unique for every ContrailVM if there are
# multiple Esxi hypervisors.
# Correct IP address is required for all other fab commands
host2 = 'root@xxxx'

router_asn = 64512
public_vn_rtgt = 10003
public_vn_subnet = "10.204.219.16/28"
ext_routers = []

host_build = 'ddivakar@10.204.216.3'

env.roledefs = {
#host2 (ContrailVM should be part of 'all')
    'all': [host1, host2],
    'cfgm': [host1],
    'openstack': [host1],
    'control': [host1],
#host2(ContrailVM should have a role of compute)
    'compute': [host1, host2],
    'collector': [host1],
    'webui': [host1],
    'database': [host1],
    'build': [host_build],
}

#Following are Esxi Hypervisor details. 
esxi_hosts = {
#Ip address of Hypervisor
 'esxi_host1' : {'ip': '10.204.216.35',
#Username and password of Esxi Hypervisor
 'username': 'root',
 'password': 'c0ntrail123',
#Uplink port of Hypervisor through which it is connected to external world
 'uplink_nic': 'vmnic2',
#Vswitch on which above uplinc exists
 'fabric_vswitch' : 'vSwitch0',
#Port group on 'fabric_vswitch' through which ContrailVM connects to external world
 'fabric_port_group' : 'contrail-fab-pg',
#Vswitch name to which all openstack VM's are hooked to
 'vm_vswitch': 'vSwitch1',
#Port group on 'vm_vswitch', which is a member of all vlans, to which ContrailVM is connected to all openstack VM's
 'vm_port_group' : 'contrail-vm-pg',
 'contrail_vm' :  {
#Below links 'host2' CotrailVM to esxi_host1 hypervisor
                   'host' : host2,
#VM name
                   'name' : 'XXXX',
#MAC addr for VM's eth0
                   'mac'  : '00:11:22:aa:bb:cc',
#Datastore on esx server *optional*
                   'datastore' : '/vmfs/volumes/datastore1/',
#Contrail VM vmdk image location *optional*
                   'image' : '/images/ContrailVM-disk1.vmdk'
                  }
 },
# Another Esxi hypervisor follows
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
}

env.hostnames = {
#Name of ContrailVM. It should match with /etc/hosts and /etc/hostname of the ContrailVM
    'all': [ 'nodec29', 'ContrailVM']
}

env.password = 'c0ntrail123'
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',

    host_build: 'c0ntrail123',
}

env.test_repo_dir='/home/ddivakar/test'
env.mail_from='ddivakar@juniper.net'
env.mail_to='ddivakar@juniper.net'


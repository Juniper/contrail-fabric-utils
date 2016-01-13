#Setting Esxi hypervisor as compute node is a three step process

#1) fab prov_esxi which provisions the Esxi with the required vswitches
#and port groups. The esxi hypervisor information is provided in
#esxi_hosts stanza as mentioned in this testbed.py file

#2) After provisioning Esxi hypervisor, ContrialVM needs to be
#instantiated as virtual machine on hypervisor manually either through
#Vsphere or Vcenter or Escicli. The vmdk disk file and ovf file are
#available along with contrial distribution

#3) After instantiating ContrailVM, the IP address need to be updated in
#this testbed.py file like any other compute node. And other fab commands
#like 'fab install_pkg_all, install_contrail, setup_all' need to be
#followed


from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.204.216.57'
host2 = 'root@10.204.216.52'
# Below is the ContrailVM on the Esxi Hypervisor. If the IP address of
# ContrailVM is not known prior to provisioning of Esxi, any dummy value
# can be written for Esxi provisioning and later modified to correct
# IP address of ContrailVM after instantiating ContrailVM on Esxi. The
# dummy value has to be unique for every ContrailVM if there are
# multiple Esxi hypervisors.
# Correct IP address is required for all other fab commands

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

#Following section contains the SRIO configuration. For a given host, it
#is a list {interface, number of Virtual functions on the interface, and
#the allowed provider networks on that interface
env.sriov = {
     host2 :[ {'interface' : 'eth0', 'VF' : 7, 'physnets' : ['physnet1', 'physnet2']}, { 'interface' : 'eth1', 'VF' : 5, 'physnets' : ['physnet3', 'physnet4']}]
}

env.hostnames = {
#Name of ContrailVM. It should match with /etc/hosts and /etc/hostname of the ContrailVM
    'all': [ 'noded2', 'nodef1']
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
}

env.password = 'c0ntrail123'
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',

    host_build: 'c0ntrail123',
}



env.test_repo_dir='/homes/ddivakar/test'
env.mail_from='ddivakar@juniper.net'
env.mail_to='ddivakar@juniper.net'


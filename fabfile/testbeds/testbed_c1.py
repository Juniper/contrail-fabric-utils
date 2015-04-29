from fabric.api import env

#Management ip addresses of hosts in the cluster
host1 = 'root@10.204.216.58'
host2 = 'root@10.204.216.59'
host3 = 'root@10.204.216.60'
host4 = 'root@10.204.216.221'
host5 = 'root@10.204.216.222'
host6 = 'root@10.204.216.223'

#External routers if any
#for eg. 
#ext_routers = [('mx1', '10.204.216.253')]
ext_routers = [('mx1', '10.204.216.253')]
router_asn = 64510
public_vn_rtgt = 10003
public_vn_subnet = "10.204.219.64/29"


#Host from which the fab commands are triggered to install and provision
host_build = 'vjoshi@10.204.216.56'

#Role definition of the hosts.
env.roledefs = {
    'all': [host1, host2, host3, host4, host5, host6],
    'cfgm': [host1,host2,host3],
    'openstack': [host2],
    'control': [host1,host2,host3],
    'compute': [host4,host5, host6],
    'collector': [host1,host2,host3],
    'webui': [host1],
    'database': [host1,host2,host3],
    'toragent': [host6],
    'tsn': [host6],
    'build': [host_build],
}

env.hostnames = {
    'all': ['nodec1', 'nodec2', 'nodec3', 'nodek1', 'nodek2', 'nodek3']
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
    host3:'ubuntu',
    host4:'ubuntu',
    host5:'ubuntu',
}

#Openstack admin password
env.openstack_admin_password = 'contrail123'

env.password = 'c0ntrail123'
#Passwords of each host
env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host3: 'c0ntrail123',
    host4: 'c0ntrail123',
    host5: 'c0ntrail123',
    host6: 'c0ntrail123',

    host_build: 'contrail123',
}

#OPTIONAL BONDING CONFIGURATION
#==============================
#Inferface Bonding
#bond= {
#    host2 : { 'name': 'bond0', 'member': ['p2p0p0','p2p0p1','p2p0p2','p2p0p3'], 'mode':'balance-xor' },
#    host5 : { 'name': 'bond0', 'member': ['p4p0p0','p4p0p1','p4p0p2','p4p0p3'], 'mode':'balance-xor' },
#}

#OPTIONAL SEPARATION OF MANAGEMENT AND CONTROL + DATA
#====================================================
#Control Interface
#control = {
#    host1 : { 'ip': '192.168.10.1/24', 'gw' : '192.168.10.254', 'device':'eth0' },
#    host2 : { 'ip': '192.168.10.2/24', 'gw' : '192.168.10.254', 'device':'p0p25p0' },
#    host3 : { 'ip': '192.168.10.3/24', 'gw' : '192.168.10.254', 'device':'eth0' },
#    host4 : { 'ip': '192.168.10.4/24', 'gw' : '192.168.10.254', 'device':'eth3' },
#    host5 : { 'ip': '192.168.10.5/24', 'gw' : '192.168.10.254', 'device':'p6p0p1' },
#    host6 : { 'ip': '192.168.10.6/24', 'gw' : '192.168.10.254', 'device':'eth0' },
#    host7 : { 'ip': '192.168.10.7/24', 'gw' : '192.168.10.254', 'device':'eth1' },
#    host8 : { 'ip': '192.168.10.8/24', 'gw' : '192.168.10.254', 'device':'eth1' },
#}

#Data Interface
#data = {
#    host2 : { 'ip': '192.161.10.1/24', 'gw' : '192.161.10.254', 'device':'bond0' },
#    host5 : { 'ip': '192.161.10.2/24', 'gw' : '192.161.10.254', 'device':'bond0' },
#}

#To disable installing contrail interface rename package
#env.interface_rename = False

#To enable multi-tenancy feature
#multi_tenancy = True

#To Enable prallel execution of task in multiple nodes
do_parallel = True
#haproxy = True
env.mail_to='vjoshi@juniper.net'
env.log_scenario='Ubuntu Icehouse multi-node Neutron Tests'
#env.test_verify_on_setup='False'

env.tor_agent = {host6:[{
                    'tor_ip':'10.204.217.38',
                    'tor_id':'1',
                    'tor_type':'ovs',
                    'tor_ovs_port':'9999',
                    'tor_ovs_protocol':'tcp',
                    'tor_tsn_ip':'10.204.216.223',
                    'tor_tsn_name':'nodek3',
                    'tor_name':'bng-contrail-qfx51-1',
                    'tor_tunnel_ip':'99.99.99.99',
                    'tor_vendor_name':'Juniper',
                    'tor_http_server_port': '9010',
                       },
{
                    'tor_ip':'10.204.216.195',
                    'tor_id':'2',
                    'tor_type':'ovs',
                    'tor_ovs_port':'6632',
                    'tor_ovs_protocol':'tcp',
                    'tor_tsn_ip':'10.204.216.223',
                    'tor_tsn_name':'nodek3',
                    'tor_name':'br0',
                    'tor_tunnel_ip':'10.204.216.195',
                    'tor_vendor_name':'openworld',
                    'tor_http_server_port': '9011',
                       }]
 }

env.test_repo_dir='/homes/vjoshi/github/mine/tor/contrail-test/'
from fabfile.testbeds import testbed_c1_extra

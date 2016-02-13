from fabric.api import env

hypervisor_type = 'XenServer'
controller_type = 'Cloudstack'

controller = 'root@10.204.216.60'
xenserver1 = 'root@10.204.216.47'
builder = 'vjoshi@10.204.216.56'

# Password used while loging into all hosts.
#All xen servers need to have same password
env.password = 'c0ntrail123'
env.cs_version = '4.3.0'
env.xen_ver = '6.2SP1'
env.xen62sp1_repo = 'http://10.204.216.51/xen62sp1/'
env.systemvm_template = 'http://10.204.216.51/cloudstack/vm_templates/systemvm64template-2014-01-14-master-xen.vhd.bz2'

env.ostypes = {
    controller: 'centos',
    xenserver1 : 'xenserver',
}

env.passwords = {
    controller: 'c0ntrail123',
    xenserver1: env.password,
    builder: 'secret',
}

env.roledefs = {
    'control': [controller],
    'compute': [xenserver1],
    'build': [builder],
    'cfgm': [controller],
    'orchestrator': [controller],
    'all' : [ controller, xenserver1],
}

env.hostnames = {
    'all': ['nodec3', 'nodea9']
}

# Below block is needed for sanity purpose alone
ext_routers = [('mx', '10.204.216.253')]
router_asn = 64512
public_vn_rtgt = 10003
public_vn_subnet = '10.204.219.0/24'

# Cloudstack specific config
config = {
    # Repos, NFS, etc.
    'nfs_share_path': '10.204.216.49:/cs-attic',
    'yum_repo_host': '10.204.216.51',
    'vm_template_url': 'http://10.204.216.51/cloudstack/vm_templates/centos64.vhd.bz2',
    'vm_template_name': 'CentOS64',
    'vsrx_template_url': 'http://10.204.216.51/cloudstack/vm_templates/juniper-vsrx-nat.vhd.bz2',
    'vsrx_template_name': 'Juniper vSRX',
    'mx_ip' : '10.204.216.253',
    'route_target' : '10003',

    # Cloud configuration
    'cloud': {
        'username': 'admin',
        'password': 'password',
        'host_password': env.password,

        'external_dns': '8.8.8.8',
        'internal_dns': '10.204.208.221',

        'pods': {
            'a6': {
                'startip': '10.204.216.230',
                'endip'  : '10.204.216.240',
                'gateway': '10.204.216.254',
                'netmask': '255.255.255.0',

                'clusters': {
                    'a6-xen1': {
                        'hypervisor_type': 'XenServer',
                        'hosts': {
                            'xen1': '10.204.216.47'
                        }
                    }
                }
            }
        },

        'public_net': {
            'startip': '10.204.219.121',
            'endip': '10.204.219.126',
            'gateway': '10.204.219.254',
            'netmask': '255.255.255.0'
        }
    }
}
env.config = config

env.test_repo_dir='/home/stack/cloudstack_sanity/test'
env.mail_to='dl-contrail-sw@juniper.net'
env.log_scenario='Cloudstack 4.3 Sanity - Combined mode'

#env.optional_services = {
#    'collector': ['snmp-collector', 'topology'],
#    'cfgm'     : ['device-manager'],
#}

from fabric.api import env

hypervisor_type = 'XenServer'
controller_type = 'Cloudstack'

orchestrator = 'root@10.204.217.12'
controller = 'root@10.204.216.60'
xenserver1 = 'root@10.204.216.47'
ubuntu_devstack = 'root@10.204.216.11'
builder = 'vjoshi@10.204.216.56'

# Password used while loging into all hosts.
#All xen servers need to have same password
env.password = 'c0ntrail123'
env.cs_version = '4.3.0_ACS'
env.cs_flavor = 'apache'
env.xen_ver = '6.2SP1'

env.ostypes = {
    orchestrator: 'cent63',
    xenserver1 : 'xenserver',
#    xenserver2 : 'xenserver',
    controller: 'centos',
    ubuntu_devstack : 'ubuntu',
}

env.passwords = {
    controller: 'c0ntrail123',
    orchestrator: 'c0ntrail123',
    xenserver1: env.password,
#    xenserver2: env.password,
    ubuntu_devstack: 'c0ntrail123',
    builder: 'secret',
}

env.roledefs = {
    'control': [controller],
    'compute': [xenserver1],
    'build': [builder],
    'cfgm': [controller],
    'orchestrator': [orchestrator],
    'all' : [ controller, xenserver1, orchestrator, ubuntu_devstack ],
}

env.hostnames = {
    'all': ['nodea9','nodec3','nodec27', 'nodea12']
}

# Cloudstack specific config
config = {
    # Repos, NFS, etc.
    'nfs_share_path': '10.204.216.49:/cs-attic',
    'yum_repo_host': '10.204.216.51',
    'cobbler_server_ip': '10.204.216.51',
    'vm_template_url': 'http://10.204.216.51/cloudstack/vm_templates/centos56-x86_64-xen.vhd.bz2',
    'vm_template_name': 'CentOS',
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
                            'xen1': '10.204.216.60'
#                            'xen2': '10.204.217.12'
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
env.xen62sp1_repo = '10.204.216.51/xen62sp1'

env.test_repo_dir='/home/stack/cloudstack_sanity/test'
env.mail_to='dl-contrail-sw@juniper.net'
env.log_scenario='ACS split setup'



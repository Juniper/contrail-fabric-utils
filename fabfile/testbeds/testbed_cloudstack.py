from fabric.api import env

hypervisor_type = 'XenServer'
controller_type = 'Cloudstack'

orchestrator = 'root@10.84.58.223'
controller = 'root@10.84.58.246'
xenserver = 'root@10.84.13.6'
xenserver2 = 'root@10.84.13.7'
builder = 'root@10.84.5.100'

# Password used while loging into all hosts
env.password = 'c0ntrail123'
env.cs_version = '4.3.0'
env.xen_ver = '6.2SP1'
env.xen62sp1_repo = 'http://10.84.5.120/cs-shared/xen62sp1'

env.roledefs = {
    'control': [controller],
    'compute': [xenserver, xenserver2],
    'build': [builder],
    'cfgm': [controller],
    'orchestrator': [orchestrator]
}

# Cloudstack specific config
config = {
    # Repos, NFS, etc.
    'nfs_share_path': '10.84.5.6:/cs-attic',
    'yum_repo_host': '10.84.5.100',
    'vm_template_url': 'http://10.84.5.120/cs-shared/cloudstack/vm_templates/centos56-x86_64-xen.vhd.bz2',
    'vm_template_name': 'CentOS 5.6',
    'vsrx_template_url': 'http://10.84.5.120/cs-shared/cloudstack/vm_templates/juniper-vsrx-nat.vhd.bz2',
    'vsrx_template_name': 'Juniper vSRX',
    'mx_ip': '10.84.18.252',
    'route_target': '1002',

    # Cloud configuration
    'cloud': {
        'username': 'admin',
        'password': 'password',
        'host_password': env.password,

        'external_dns': '10.84.5.100',
        'internal_dns': '10.84.5.100',

        'pods': {
            'a6': {
                'startip': '10.84.13.1',
                'endip': '10.84.13.253',
                'gateway': '10.84.13.254',
                'netmask': '255.255.255.0',

                'clusters': {
                    'a6-xen1': {
                        'hypervisor_type': 'XenServer',

                        'hosts': {
                            'xen1': '10.84.13.06',
                            'xen2': '10.84.13.07'
                        }
                    }
                }
            }
        },

        'public_net': {
            'startip': '10.84.59.80',
            'endip': '10.84.59.95',
            'gateway': '10.84.59.253',
            'netmask': '255.255.255.0'
        }
    }
}
env.config = config

#env.optional_services = {
#    'collector': ['snmp-collector', 'topology'],
#    'cfgm'     : ['device-manager'],
#}

from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.84.5.27'
host2 = 'root@10.84.5.28'

ext_routers = []
router_asn = 64512
public_vn_rtgt = 10000

host_build = 'nsheth@10.84.5.31'

env.roledefs = {
    'all':       [host1, host2],
    'cfgm':      [host1],
    'openstack': [host1],
    'webui':     [host1],
    'control':   [host1, host2],
    'collector': [host1],
    'database':  [host1],
    'compute':   [host1, host2],
    'build': [host_build],
}

env.hostnames = {
    'all': ['a1s27', 'a1s28']
}

env.ostypes = {
    host1:'ubuntu',
    host2:'ubuntu',
}

env.passwords = {
    host1: 'c0ntrail123',
    host2: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

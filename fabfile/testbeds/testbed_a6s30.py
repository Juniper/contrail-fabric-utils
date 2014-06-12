from fabric.api import env

os_username = 'admin'
os_password = 'contrail123'
os_tenant_name = 'demo'

host1 = 'root@10.84.13.30'

ext_routers = [('mx1', '10.84.11.253'), ('mx2', '10.84.11.252')]
router_asn = 64512
public_vn_rtgt = 10000

host_build = 'nsheth@10.84.5.31'

env.roledefs = {
    'all':       [host1],
    'cfgm':      [host1],
    'openstack': [host1],
    'webui':     [host1],
    'control':   [host1],
    'collector': [host1],
    'database':  [host1],
    'compute':   [host1],
    'build': [host_build],
}

env.hostnames = {
    'all': ['a6s30']
}

env.ostypes = {
    host1:'ubuntu',
}

env.passwords = {
    host1: 'c0ntrail123',
    host_build: 'c0ntrail123',
}

from fabric.api import env

env.tor_hosts={
'10.204.217.38': [{ 'tor_port': 'ge-0/0/0',
                    'host_port' : 'p1p2',
                    'mgmt_ip' : '10.204.217.16',
                    'username' : 'root',
                    'password' : 'c0ntrail123',
                  }],
'10.204.216.195': [{ 'tor_port': 'torport1',
                    'host_port' : 'hostport1',
                    'mgmt_ip' : '10.204.216.195',
                    'username' : 'root',
                    'password' : 'c0ntrail123',
                  }]
}

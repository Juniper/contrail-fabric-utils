"""Config module that is use to share data acreoss other modules in the
fabric-utils package.
"""
import sys
import datetime
from netaddr import *
from time import sleep, strftime

import importlib
from fabric.api import *
from fabric.state import output, connections
from fabric.operations import get, put
from fabric.exceptions import CommandTimeout
from fabric.contrib import files

# Don't add any new testbeds here. Create new files under fabfile/testbeds
# and copy/link the testbed.py file from/to the one you want to use.
#
# Note that fabfile/testbeds/testbed.py MUST NOT be added to the repository.
if hasattr(env, 'mytestbed'):
    testbed = importlib.import_module('fabfile.testbeds.%s' % env.mytestbed)
else:
    import testbeds.testbed as testbed

# Fabric 1.7.0 and above expects the keys/host_strings in env.passwords to be with :port
# Adding host_strings with :22, to make the fabric-utils compatabile with it.
if hasattr(env, 'passwords'):
    for key in env.passwords.keys():
        env.passwords.update({key+':22' : env.passwords[key]})

# Set default rabbit role
env.roledefs['rabbit'] = []

# Set default openstack role to empty list,
# If env.roledefs['openstack'] is not set in the testbed.py
if not env.roledefs.get('openstack', None):
    env.roledefs['openstack'] = []

if env.roledefs.get('contrail-controller'):
    env.roledefs['cfgm'] = env.roledefs.get('contrail-controller')
    env.roledefs['webui'] = env.roledefs.get('contrail-controller')
    env.roledefs['control'] = env.roledefs.get('contrail-controller')
    env.roledefs['database'] = env.roledefs.get('contrail-analyticsdb')
    env.roledefs['collector'] = env.roledefs.get('contrail-analytics')
    env.roledefs['compute'] = env.roledefs.get('contrail-compute')

class Logger(object):
    def __init__(self, filename="fabric.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "a")
        self.plus_timestamp = True

    def write(self, message):
        time_stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')
        if '\n' in message:
            self.plus_timestamp = True
        if self.plus_timestamp:
            message = message.replace('\n', '\n%s: ' %time_stamp)
            self.plus_timestamp = False

        self.terminal.write(message)
        self.log.write(message)

    def isatty(self):
        return self.terminal.isatty() 

    def flush(self):
        self.terminal.flush()
        self.log.flush()

class StdErrLogger(Logger):
    def __init__(self, filename="fabric.log"):
        super(StdErrLogger, self).__init__(filename)
        self.terminal = sys.stderr


fabtasks = [fabtask.split(':')[0] for fabtask in env.tasks]
ts = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
sys.stdout = Logger('_'.join(fabtasks) + '_' + ts + '.log')
sys.stderr = StdErrLogger('_'.join(fabtasks) + '_' + ts + '.log')


INSTALLER_DIR = '/opt/contrail/bin'
UTILS_DIR = '/opt/contrail/utils'
BUG_DIR = '/volume/labcores/contrail/bugs'
RPMS_DIR = '~/rpms'
env.disable_known_hosts=True

CONTROLLER_TYPE = 'Openstack'
if hasattr(env, 'orchestrator'):
    if env.orchestrator == 'vcenter':
        CONTROLLER_TYPE = 'vcenter'
# Import cloudstack functions for appropriate testbeds
if hasattr(testbed, 'controller_type'):
    if testbed.controller_type == 'Cloudstack':
        import cloudstack
        CONTROLLER_TYPE = testbed.controller_type

# Import xenserver functions for appropriate testbeds
if hasattr(testbed, 'controller_type'):
    if testbed.hypervisor_type == 'XenServer':
        import xenserver

# Choose the right decorator(parallel/serial) for execution
EXECUTE_TASK = serial
if hasattr(testbed, 'do_parallel'):
    if testbed.do_parallel:
        EXECUTE_TASK = parallel(pool_size=20)

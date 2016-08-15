"""
This package implements a set of `fabric <http://www.fabfile.org>` tasks to 
provision a Juniper VNS openstack cluster. These tasks can be used after the
cluster is imaged to launch role specific services. To perform this a testbed
specification file has be provided (for eg. `like this <testbeds/testbed_multibox_example.py>`
and `this <testbeds/testbed_singlebox_example.py>`).

This package contains tasks and utils pacakges.
	tasks : Package containing various fab tasks in specific modules.
	utils : Package containing common api's used by the tasks package..
"""

# Config module at fabfile/config.py to import testbed file and hold global
# vars that are shared across various modules in tasks and utisl packages. 
from  config import *

# Fabric tasks
from tasks.ntp import *
from tasks.tester import *
from tasks.install import *
from tasks.uninstall import *
from tasks.storage.install import *
from tasks.syslogs import *
from tasks.helpers import *
from tasks.provision import *
from tasks.storage.provision import *
from tasks.upgrade import *
from tasks.services import *
from tasks.misc import *
from tasks.storage.misc import *
from tasks.rabbitmq import *
from tasks.ha import *
from tasks.zookeeper import *
from tasks.backup_restore import *
from tasks.kernel import *
from tasks.issu_process import *
from tasks.ssl import *

# For contrail use
try:
    from contraillabs.setup import *
    from contraillabs.rdo import *
    from contraillabs.utils import *
    from contraillabs.vtb.vm import *
except ImportError:
    pass

@task
def help(task_name):
    try:
       print("\n\nTask is at module: %s" % globals()[task_name].__module__)
       print("\n\nUse: %s" % globals()[task_name].__doc__)
    except KeyError:
        print("\n\nUnknown task: %s" % task_name)

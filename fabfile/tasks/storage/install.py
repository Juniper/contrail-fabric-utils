import os
import re
import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.tasks.install import yum_install,  apt_install

@task
@EXECUTE_TASK
@roles('storage-master')
def install_storage_master():
    """Installs storage pkgs in all nodes defined in storage-master role."""
    execute("install_storage_master_node", env.host_string)

@task
def install_storage_master_node(*args):
    """Installs storage pkgs in one or list of nodes. USAGE:fab install_openstack_storage_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-storage']
            if detect_ostype() == 'Ubuntu':
                apt_install(pkg)
            else:
                yum_install(pkg)

@task
@EXECUTE_TASK
@roles('storage-compute')
def install_storage_compute():
    """Installs storage pkgs in all nodes defined in storage-compute role."""
    execute("install_storage_compute_node", env.host_string)

@task
def install_storage_compute_node(*args):
    """Installs storage pkgs in one or list of nodes. USAGE:fab install_compute_storage_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            pkg = ['contrail-storage']
            if detect_ostype() == 'Ubuntu':
                apt_install(pkg)
            else:
                yum_install(pkg)

@roles('build')
@task
def install_storage():
    """Installs required storage packages in nodes as per the role definition.
    """
    execute(install_storage_master)
    execute(install_storage_compute)

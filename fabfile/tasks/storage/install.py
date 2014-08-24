import os
import re
import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.tasks.install import yum_install,  apt_install


@task
@parallel(pool_size=20)
@roles('all')
def install_storage_pkg_all(pkg):
    """Installs any rpm/deb in storage-master/storage-compute nodes."""
    host_strings = copy.deepcopy(env.roledefs['storage-master'])
    dummy = [host_strings.append(storage_compute_node)
             for storage_compute_node in env.roledefs['storage-compute']]
    execute('install_storage_pkg_node', pkg, *host_strings)

@task
def install_storage_pkg_node(pkg, *args):
    """Installs any rpm/deb in storage-master/storage-compute node."""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            build = get_build('contrail-storage-packages')
            if build and build in pkg:
                print "Package %s already installed in the node(%s)." % (pkg, host_string)
                continue
            pkg_name = os.path.basename(pkg)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name))
            if pkg.endswith('.rpm'):
                run("yum --disablerepo=* -y localinstall %s/%s" % (temp_dir, pkg_name))
            elif pkg.endswith('.deb'):
                run("dpkg -i %s/%s" % (temp_dir, pkg_name))



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
            pkg = ['contrail-storage','contrail-web-storage']
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

@task
@EXECUTE_TASK
@roles('all')
def create_storage_repo():
    host_strings = copy.deepcopy(env.roledefs['storage-master'])
    dummy = [host_strings.append(storage_compute_node)
             for storage_compute_node in env.roledefs['storage-compute']]
    execute('create_storage_repo_node', *host_strings)

@task
def create_storage_repo_node(*args):
    for host_string in args:
        with  settings(host_string=host_string, warn_only=True):
            run("sudo /opt/contrail/contrail_packages/setup_storage.sh")

@roles('build')
@task
def install_storage():
    """Installs required storage packages in nodes as per the role definition.
    """
    execute(create_storage_repo)
    execute(install_storage_master)
    execute(install_storage_compute)

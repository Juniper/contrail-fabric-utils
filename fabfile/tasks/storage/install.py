import os
import re
import copy
import tempfile
from decimal import *

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.tasks.install import yum_install,  apt_install

def apt_install_overwrite(debs):
    cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes --allow-unauthenticated -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confnew" install '
    if detect_ostype() in ['ubuntu']:
        for deb in debs:
            sudo(cmd + deb)

@task
@parallel(pool_size=20)
@roles('all')
def install_storage_pkg_all(pkg):
    """Installs any rpm/deb in storage-master/storage-compute nodes."""
    execute('install_storage_pkg_node', pkg, env.host_string)

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
            sudo('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
            if pkg.endswith('.rpm'):
                sudo("yum --disablerepo=* -y localinstall %s/%s" % (temp_dir, pkg_name))
            elif pkg.endswith('.deb'):
                sudo("dpkg -i %s/%s" % (temp_dir, pkg_name))



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
            if detect_ostype() == 'ubuntu':
                apt_install_overwrite(pkg)
            else:
                yum_install(pkg)

@task
@EXECUTE_TASK
@roles('webui')
def install_storage_webui():
    """Installs storage webui pkgs in all nodes defined in webui role."""
    if env.roledefs['webui']:
            execute("install_storage_webui_node", env.host_string)


@task
def install_storage_webui_node(*args):
    """Installs storage pkgs in one or list of nodes. USAGE:fab install_storage_webui:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-web-storage']
            if detect_ostype() == 'ubuntu':
                apt_install_overwrite(pkg)
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
            if detect_ostype() == 'ubuntu':
                apt_install_overwrite(pkg)
            else:
                yum_install(pkg)

@task
@EXECUTE_TASK
@roles('all')
def create_storage_repo():
    execute('create_storage_repo_node', env.host_string)

@task
def create_storage_repo_node(*args):
    for host_string in args:
        with  settings(host_string=host_string, warn_only=True):
            sudo("sudo /opt/contrail/contrail_packages/setup_storage.sh")

@roles('build')
@task
def install_storage():
    """Installs required storage packages in nodes as per the role definition.
    """
    execute(create_storage_repo)
    execute(install_storage_master)
    execute(install_storage_compute)
    execute(install_storage_webui)


@task
@roles('build')
def upgrade_storage(from_rel, pkg):
    """upgrades all the contrail pkgs in all nodes."""
    to_rel = get_release()
    if Decimal(to_rel) > Decimal(from_rel):
        execute('install_storage_pkg_all', pkg)
        execute('install_storage')
        execute('setup_upgrade_storage')
    else:
        raise RuntimeError("Upgrade not supported from release %s to %s" % (from_rel, to_rel))

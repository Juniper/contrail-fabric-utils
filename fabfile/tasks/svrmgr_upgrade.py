import os
import copy
import re
import sys
import tempfile

from fabric.api import settings, run
from fabric.api import hosts, task
from fabric.api import env
from fabric.api import local, put, get
from fabric.tasks import execute
from datetime import datetime as dt


env.password = 'c0ntrail123'


@task
def upgrade_svrmgr(host_string=None, pkg=None, mode='soft'):
    """Upgrade svrmgr pkg in the given node. USAGE:fab install_svrmgr:user@1.1.1.1, <pkg>"""
    if not host_string or not pkg:
        usage_server()
    execute("install_epel", host_string)
    execute("uninstall_svrmgr", host_string, mode)
    execute("install_svrmgr", pkg, host_string, mode)
    execute("check_server_installed", host_string, pkg)

@task
def upgrade_svrmgr_client(host_string=None, pkg=None, mode='soft'):
    """Upgrade svrmgr client pkg in the given node. USAGE:fab install_svrmgr_client:user@1.1.1.1, <pkg>"""
    if not host_string or not pkg:
        usage_client()
    execute("uninstall_svrmgr_client", host_string, mode)
    execute("install_svrmgr_client", pkg, host_string, mode)
    execute("check_client_installed", host_string, pkg)

@task
def install_svrmgr(pkg, host_string, mode):
    """install svrmgr pkgs in one or list of nodes"""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            pkg_name = os.path.basename(pkg)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name))
            if pkg.endswith('.rpm'):
                run("yum -y localinstall %s/%s" % (temp_dir, pkg_name))
            elif pkg.endswith('.deb'):
                run("dpkg -i %s/%s" % (temp_dir, pkg_name))
            if mode=='hard':
                run('service cobblerd stop')
                run('service httpd stop')
            run('service contrail-server-manager stop')
            restore_config(host_string)
            run('service contrail-server-manager start')

@task
def install_svrmgr_client(pkg, host_string, mode):
    """install svrmgr client pkg in one or list of nodes"""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            pkg_name = os.path.basename(pkg)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name))
            if pkg.endswith('.rpm'):
                run("yum -y localinstall %s/%s" % (temp_dir, pkg_name))
            elif pkg.endswith('.deb'):
                run("dpkg -i %s/%s" % (temp_dir, pkg_name))
            restore_client_config(host_string)

@task
def install_epel(host_string):
    """Install epel in node"""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            epel = check_epel(host_string)
            if not epel: 
                run('wget http://buaya.klas.or.id/epel/6/i386/epel-release-6-8.noarch.rpm')
                if pkg.endswith('.rpm'):
                    run('yum -y localinstall epel-release-6-8.noarch.rpm')
                elif pkg.endswith('.deb'):
                    run("dpkg -i %s/%s" % (temp_dir, pkg_name))

@task
def uninstall_svrmgr(host_string, mode):
    """uninstall svmgr in one or list of nodes"""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            save_config(host_string)
            archive_config(host_string)
            run('service contrail-server-manager stop')
            if mode=='hard':
                run('service puppet stop')
                run('service puppetmaster stop')
                run('service cobblerd stop')
            pkg_name=get_sm_pkg(host_string)
            if pkg_name:
              run('rpm -e %s' %pkg_name)
            if mode=='hard':
                run('yum -y remove puppet')
                run('yum -y remove cobbler')
            run('rm -rf /etc/contrail_smgr /opt/contrail/server_manager')

@task
def uninstall_svrmgr_client(host_string, mode):
    """uninstall svmgr_client in one or list of nodes"""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            save_config(host_string)
            pkg_name=get_sm_client_pkg(host_string)
            if pkg_name:
              run('rpm -e %s' %pkg_name)

def get_sm_pkg(host):
    """get pkg name of the contrail-server-manager"""
    with settings(host_string=host):
        with settings(warn_only=True):
            output = run('rpm -qa | grep contrail-server-manager | grep -v client')
            pkg=None
            tmp1 = re.search( r'(contrail-server-manager.*noarch)' ,output,  re.M|re.I)
            if tmp1:
              pkg = tmp1.group()
            return pkg

def get_sm_client_pkg(host):
    """get pkg name of the contrail-server-manager"""
    with settings(host_string=host):
        with settings(warn_only=True):
            output = run('rpm -qa | grep contrail-server-manager-client')
            pkg=None
            tmp1 = re.search( r'(contrail-server-manager-client.*noarch)' ,output,  re.M|re.I)
            if tmp1:
              pkg = tmp1.group()
            return pkg

def check_epel(host):
    """check installed epel"""
    with settings(host_string=host):
        with settings(warn_only=True):
            output = run('rpm -qa | grep epel-release')
            pkg=None
            tmp1 = re.search( r'(epel-release-.*noarch)' ,output,  re.M|re.I)
            if tmp1:
              pkg = tmp1.group()
            return pkg

@task
def check_server_installed(host, new_pkg):
    """check installed server manager pkg"""
    with settings(host_string=host):
        with settings(warn_only=True):
            output = run('rpm -qa | grep contrail-server-manager | grep -v client')
            pkg = output.rstrip('\r\n')
            if pkg not in new_pkg:
              raise RuntimeError('Server package mismatch .')

@task
def check_client_installed(host, new_pkg):
    """check installed epel"""
    with settings(host_string=host):
        with settings(warn_only=True):
            output = run('rpm -qa | grep contrail-server-manager-client')
            pkg = output.rstrip('\r\n')
            if pkg not in new_pkg:
              raise RuntimeError('Client package mismatch .')

def restore_config(host_string):
    """Restore server-manager specific config files."""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            save_dir = "/tmp/contrail-smgr-save"
            run('\cp -rf %s/dhcp.template /etc/cobbler/dhcp.template' %save_dir)
            run('\cp -rf %s/named.template /etc/cobbler/named.template' %save_dir)
            run('\cp -rf %s/settings /etc/cobbler/settings' %save_dir)
            run('\cp -rf %s/sm-config.ini /opt/contrail/server_manager/' %save_dir)
            run('\cp -rf %s/sm-client-config.ini /opt/contrail/server_manager/client/' %save_dir)

def restore_client_config(host_string):
    """Restore server-manager specific config files."""
    with settings(host_string=host_string):
        with settings(warn_only=True):
            save_dir = "/tmp/contrail-smgr-save"
            run('\cp -rf %s/sm-client-config.ini /opt/contrail/server_manager/client/' %save_dir)

def save_config(host_string):
    """save server manager specific config """
    with settings(host_string=host_string):
        with settings(warn_only=True):
            save_dir = "/tmp/contrail-smgr-save"
            run('mkdir -p %s' %save_dir)
            run('\cp -rf /etc/cobbler/dhcp.template %s' %save_dir)
            run('\cp -rf /etc/cobbler/named.template %s' %save_dir)
            run('\cp -rf /etc/cobbler/settings %s' %save_dir)
            run('\cp -rf /opt/contrail/server_manager/sm-config.ini %s' %save_dir)
            run('\cp -rf /opt/contrail/server_manager/client/sm-client-config.ini %s' %save_dir)
            run('\cp -rf /etc/contrail_smgr/smgr_data.db %s' %save_dir)

def archive_config(host_string):
    """archive server manager specific config """
    with settings(host_string=host_string):
        with settings(warn_only=True):
            timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
            save_dir = "/tmp/contrail-smgr-save-%s" %timestamp
            run('mkdir -p %s' %save_dir)
            run('\cp -rf /etc/cobbler/dhcp.template %s' %save_dir)
            run('\cp -rf /etc/cobbler/named.template %s' %save_dir)
            run('\cp -rf /etc/cobbler/settings %s' %save_dir)
            run('\cp -rf /opt/contrail/server_manager/sm-config.ini %s' %save_dir)
            run('\cp -rf /opt/contrail/server_manager/client/sm-client-config.ini %s' %save_dir)
            run('\cp -rf /etc/contrail_smgr/smgr_data.db %s' %save_dir)

def usage():
    print "USAGE:  fab upgrade_svrmgr:user@1.1.1.1, <pkg>"
    sys.exit(1)

def usage_client():
    print "USAGE:  fab upgrade_svrmgr_client:user@1.1.1.1, <pkg>"
    sys.exit(1)

"""Private contrail task for setting up RDO in the openstack node."""

import os

from fabfile.config import *
from fabfile.utils.host import get_keystone_ip
from fabfile.utils.cluster import reboot_nodes
from fabfile.utils.fabos import get_as_sudo

@task
@roles('build')
def get_packages_from_node(host_string, *pkgnames):
    available_pkgs = []
    downloaded = []
    missing = []
    # verify given packages are available
    for pkgname in pkgnames:
        with settings(host_string=host_string):
            is_pkg_available = sudo('find /opt/contrail/ -name %s*.rpm' % pkgname)
        if is_pkg_available.succeeded:
            available_pkgs.append(is_pkg_available)
        else:
            missing.append(pkgname)
            print 'WARNING: Package file for package (%s) is missing in Node (%s)' % (pkgname, host_string)
    if len(missing) != 0:
        raise RuntimeError('Package file for below packages are missing'
                           ' in CFGM (%s): \n%s' % (host_string, '\n'.join(missing)))

    # download available packages to tempdir
    tempdir = local('mktemp -d', capture=True)
    with settings(host_string=host_string):
        for available_pkg in available_pkgs:
            get_as_sudo(available_pkg, tempdir)
            pkg_file_name = os.path.basename(available_pkg)
            downloaded.append(os.path.join(tempdir, pkg_file_name))
    return downloaded

@task
@roles('openstack')
def install_pkg_from_node(host_string, *pkgnames):
    available_pkgs = execute(get_packages_from_node, host_string, *pkgnames)
    available_pkg_files = available_pkgs[env.roledefs['build'][0]]
    # copy/install in openstack
    tempdir = sudo('mktemp -d')
    for pkg_file in available_pkg_files:
        put(pkg_file, tempdir)
        pkg_file_name = os.path.basename(pkg_file)
        with cd(tempdir):
            sudo('yum -y localinstall %s' % pkg_file_name)
            sudo('rm -f %s' % pkg_file_name)
    sudo('rm -r %s' % tempdir)

@task
@roles('openstack')
def fix_yum_repos():
    """ copy local repo locations """
    put('fabfile/contraillabs/repo/rhel70_rdo.repo', '/etc/yum.repos.d/cobbler-config.repo', use_sudo=True)
    sudo('yum clean all')


@task
@roles('openstack')
def install_rhosp5_repo():
    """ copy local rhosp5 repo locations """
    put('fabfile/contraillabs/repo/rhosp5_local.repo', '/etc/yum.repos.d/rhosp5_local.repo', use_sudo=True)
    sudo('yum clean all')

@task
@roles('openstack')
def install_rhosp6_repo():
    """ copy local rhosp6 repo locations """
    put('fabfile/contraillabs/repo/rhosp6_local.repo', '/etc/yum.repos.d/rhosp6_local.repo', use_sudo=True)
    sudo('yum clean all')

@task
@roles('openstack')
def update_rhosp_node(reboot='True'):
    with settings(warn_only=True):
        sudo("yum -y install yum-utils")
        sudo("yum -y install kernel-headers")
        sudo("yum update -y")
        print "[%s]: Disable NeworkManager and reboot" % env.host_string
        sudo("systemctl stop NetworkManager")
        sudo("systemctl disable NetworkManager")
    if reboot == 'True':
        execute(reboot_nodes, env.host_string)
        pass
    else:
        print '[%s]: WARNING: Skipping Reboot as reboot!=True. '\
              'Reboot manually to avoid misconfiguration!' % env.host_string

@task
@roles('openstack')
def setup_rhosp_node():
    """Set up RHOSP Node"""
    sudo('sudo yum install -y openstack-packstack')
    sudo('packstack --allinone --mariadb-pw=juniper123 --use-epel=n --nagios-install=n')
    openstack_password = getattr(env, 'openstack_admin_password', 'contrail123')
    sudo('source keystonerc_admin && keystone user-password-update --pass %s admin' % openstack_password)
    sudo("sed -i -e 's/export OS_PASSWORD=.*/export OS_PASSWORD=%s/' keystonerc_admin " % openstack_password)
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    sudo("service openstack-nova-compute stop")
    sudo("chkconfig openstack-nova-compute off")
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    sudo("service neutron-server stop")
    sudo("chkconfig neutron-server off")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    with settings(warn_only=True):
        openstackrc_file = sudo("ls /etc/contrail/openstackrc")
        if openstackrc_file.return_code != 0:
            sudo('mkdir -p /etc/contrail/')
            sudo("ln -s /root/keystonerc_admin /etc/contrail/openstackrc")
    cfgm_0_ip = testbed.env['roledefs']['cfgm'][0].split('@')[1]
    keystone_ip = get_keystone_ip()
    sudo("source /etc/contrail/openstackrc; nova service-disable $(hostname) nova-compute")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_url http://%s:9696" % cfgm_0_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:35357/v2.0" % keystone_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  compute_driver nova.virt.libvirt.LibvirtDriver")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  novncproxy_port 5999")
    sudo("service openstack-nova-api restart")
    sudo("service openstack-nova-conductor restart")
    sudo("service openstack-nova-scheduler restart")
    sudo("service openstack-nova-novncproxy restart")
    sudo("service openstack-nova-consoleauth restart")
    sudo("iptables --flush")
    sudo("sudo service iptables stop; echo pass")
    sudo("sudo service ip6tables stop; echo pass")
    sudo("sudo systemctl stop firewalld; echo pass")
    sudo("sudo systemctl status firewalld; echo pass")
    sudo("sudo chkconfig firewalld off; echo pass")
    sudo("sudo /usr/libexec/iptables/iptables.init stop; echo pass")
    sudo("sudo /usr/libexec/iptables/ip6tables.init stop; echo pass")
    sudo("sudo service iptables save; echo pass")
    sudo("sudo service ip6tables save; echo pass")
    sudo("mkdir -p /var/crashes")

    execute(install_pkg_from_node, cfgm_0_ip, 'contrail-nova-networkapi')
    steps = "\n\n\n"
    steps += "="*160
    steps += "\nSteps to bring up contrail with the RHOSP:\n\
                1. Get the admin_token from /etc/keystone/keystone.conf of the openstack node and populate it as service_token in the testbed.py.\n\
                2. fab install_without_openstack (This step can be executed even before fab setup_rdo)\n\
                3. fab setup_without_openstack\n"
    steps += "="*160
    print steps

@task
@roles('openstack')
def setup_rdo(rdo_url='https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm'):
    """Set up RDO in the openstack node"""
    with settings(warn_only=True):
         sudo('sudo yum -y install %s' % rdo_url)
    execute(fix_yum_repos)
    with settings(warn_only=True):
        sudo('sudo yum install -y openstack-packstack')
    sudo('packstack --allinone --mariadb-pw=juniper123 --use-epel=n --nagios-install=n')
    openstack_password = getattr(env, 'openstack_admin_password', 'contrail123')
    sudo('source keystonerc_admin && keystone user-password-update --pass %s admin' % openstack_password)
    sudo("sed -i -e 's/export OS_PASSWORD=.*/export OS_PASSWORD=%s/' keystonerc_admin " % openstack_password)
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    sudo("service openstack-nova-compute stop")
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    sudo("service neutron-server stop")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    with settings(warn_only=True):
        openstackrc_file = sudo("ls /etc/contrail/openstackrc")
        if openstackrc_file.return_code != 0:
            sudo('mkdir -p /etc/contrail/')
            sudo("ln -s ~/keystonerc_admin /etc/contrail/openstackrc")
    cfgm_0_ip = testbed.env['roledefs']['cfgm'][0].split('@')[1]
    keystone_ip = get_keystone_ip()
    sudo("source /etc/contrail/openstackrc; nova service-disable $(hostname) nova-compute")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_url http://%s:9696" % cfgm_0_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:35357/v2.0" % keystone_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  compute_driver nova.virt.libvirt.LibvirtDriver")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  novncproxy_port 5999")
    sudo("service openstack-nova-api restart")
    sudo("service openstack-nova-conductor restart")
    sudo("service openstack-nova-scheduler restart")
    sudo("service openstack-nova-novncproxy restart")
    sudo("service openstack-nova-consoleauth restart")
    sudo("iptables --flush")
    sudo("sudo service iptables stop; echo pass")
    sudo("sudo service ip6tables stop; echo pass")
    sudo("sudo systemctl stop firewalld; echo pass")
    sudo("sudo systemctl status firewalld; echo pass")
    sudo("sudo chkconfig firewalld off; echo pass")
    sudo("sudo /usr/libexec/iptables/iptables.init stop; echo pass")
    sudo("sudo /usr/libexec/iptables/ip6tables.init stop; echo pass")
    sudo("sudo service iptables save; echo pass")
    sudo("sudo service ip6tables save; echo pass")

    steps = "\n\n\n"
    steps += "="*160
    steps += "\nSteps to bring up contrail with the RDO:\n\
                1. Get the admin_token from /etc/keystone/keystone.conf of the openstack node and populate it as service_token in the testbed.py.\n\
                2. fab install_without_openstack (This step can be executed even before fab setup_rdo)\n\
                3. fab setup_without_openstack\n"
    steps += "="*160
    print steps

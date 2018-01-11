import os
import re
import copy
import time
import glob
import tarfile
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabric.contrib.files import exists
from fabfile.utils.cluster import is_lbaas_enabled, get_orchestrator,\
     reboot_nodes, get_mode
from fabfile.utils.install import get_compute_ceilometer_pkgs,\
     get_compute_pkgs, get_ceilometer_plugin_pkgs, get_openstack_pkgs, \
     get_openstack_ceilometer_pkgs, create_yum_repo_from_tgz_node, \
     create_apt_repo_from_tgz_node, get_config_pkgs, get_vcenter_plugin_pkg, \
     get_vcenter_compute_pkgs, get_vcenter_plugin_depend_pkgs, \
     get_net_driver_pkgs
from fabfile.utils.host import get_from_testbed_dict,\
    get_openstack_internal_vip, get_hypervisor, get_env_passwords
from fabfile.tasks.helpers import reboot_node
from fabfile.utils.analytics import is_ceilometer_install_supported, \
    is_ceilometer_compute_install_supported, \
    is_ceilometer_contrail_plugin_install_supported

SERVICE_NAMES = {
    'keystone' : {'centos' : 'openstack-keystone',
                  'centoslinux' : 'openstack-keystone'}
}

@task
@parallel(pool_size=20)
@roles('all')
def install_rpm_all(rpm):
    """Installs any rpm in all nodes."""
    execute('install_pkg_node', rpm, env.host_string)

@task
@parallel(pool_size=20)
@roles('all')
def install_deb_all(deb):
    """Installs any deb in all nodes."""
    execute('install_pkg_node', deb, env.host_string)

@task
@parallel(pool_size=20)
@roles('all')
def install_pkg_all(pkg):
    """Installs any rpm/deb package in all nodes."""
    execute('install_pkg_node', pkg, env.host_string)

@task
@roles('openstack')
def install_contrail_openstack(*tgzs, **kwargs):
    """install contrail-cloud-openstack on openstack nodes."""
    if env.roledefs['openstack']:
        execute("create_install_repo_from_tgz_node", env.host_string, *tgzs, **kwargs)
        execute("install_openstack")
        execute(update_keystone_log)

@task
@parallel(pool_size=20)
def install_contrail_vcenter_plugin(pkg, *args):
    """Installs any rpm/deb package in all nodes."""
    if not pkg:
        print "Error:No vcenter plugin pkg, aborting"
        exit(1)

    depend_pkgs = get_vcenter_plugin_depend_pkgs()

    if args:
        host_list = args
    else:
       if get_orchestrator() is 'vcenter':
            host_list = env.roledefs['cfgm'][:]
       else:
            if 'vcenter_compute' in env.roledefs:
                host_list = env.roledefs['vcenter_compute'][:]

    for host_string in host_list:
         with settings (host_string=host_string, warn_only=True):
            apt_install(depend_pkgs)
            if type(pkg) is list:
                 #Invoked from install_cfgm or install_vcenter_compute
                 #pkg is passed as a list
                 apt_install(pkg)
            else:
                 #Invoked when 'fab install_contrail_vcenter_plugin'
                 #is used with the vcenter-plugin deb as argument
                 execute('install_pkg_node', pkg, env.host_string)
            execute('install_contrail_vcenter_plugin_node', env.host_string)

@task
def install_contrail_vcenter_plugin_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo('cd /opt/contrail/contrail_vcenter_plugin_install_repo/; dpkg -i *.deb')

@task
@roles('build')
def install_pkg_all_without_openstack(pkg):
    """Installs any rpm/deb package in all nodes excluding openstack node."""
    host_strings = copy.deepcopy(env.roledefs['all'])
    dummy = [host_strings.remove(openstack_node)
             for openstack_node in env.roledefs['openstack']]
    execute('install_pkg_node', pkg, *host_strings)

@task
def install_pkg_node(pkg, *args):
    """Installs any rpm/deb in one node."""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            # Get the package name from .rpm | .deb
            if pkg.endswith('.rpm'):
                pkgname = local('rpm -qp --queryformat "%%{NAME}" %s' % pkg, capture=True)
                print "Package Name (%s)" % pkgname
                pkg_version = local('rpm -qp --queryformat "%%{VERSION}-%%{RELEASE}" %s' % pkg, capture=True)
                print "Package Version (%s)" % pkg_version
            elif pkg.endswith('.deb'):
                pkgname = local("dpkg -I %s | grep -Po '^\s+Package:\s+\K.*'" % pkg, capture=True)
                pkg_version = local("dpkg -I %s | grep -Po '^\s+Version:\s+\K.*'" % pkg, capture=True)
            if pkgname:
                versions = get_pkg_version_release(pkgname)
                if versions and pkg_version in versions:
                    print "Package (%s) already installed in the node (%s)." % (pkg, host_string)
                    continue
            pkg_name = os.path.basename(pkg)
            temp_dir= tempfile.mkdtemp()
            sudo('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
            if pkg.endswith('.rpm'):
                sudo("yum --disablerepo=* -y localinstall %s/%s" % (temp_dir, pkg_name))
            elif pkg.endswith('.deb'):
                sudo("dpkg -i %s/%s" % (temp_dir, pkg_name))


def upgrade_rpm(rpm):
    rpm_name = os.path.basename(rpm)
    temp_dir= tempfile.mkdtemp()
    sudo('mkdir -p %s' % temp_dir)
    put(rpm, '%s/%s' % (temp_dir, rpm_name), use_sudo=True)
    sudo("rpm --upgrade --force -v %s/%s" % (temp_dir, rpm_name))

@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_rpm_cfgm(rpm):
    """Upgrades any rpm in cfgm nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('database')
def upgrade_rpm_database(rpm):
    """Upgrades any rpm in database nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('openstack')
def upgrade_rpm_openstack(rpm):
    """Upgrades any rpm in openstack nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('collector')
def upgrade_rpm_collector(rpm):
    """Upgrades any rpm in collector nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('compute')
def upgrade_rpm_compute(rpm):
    """Upgrades any rpm in compute nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('control')
def upgrade_rpm_control(rpm):
    """Upgrades any rpm in control nodes."""
    upgrade_rpm(rpm)

@task
@EXECUTE_TASK
@roles('webui')
def upgrade_rpm_webui(rpm):
    """Upgrades any rpm in webui nodes."""
    upgrade_rpm(rpm)

@task
@parallel(pool_size=20)
@roles('all')
def upgrade_rpm_all(rpm):
    """Upgrades any rpm in all nodes."""
    upgrade_rpm(rpm)

@roles('build')
@task
def install_and_setup_all():
    """Installs and provisions all the contrail services as per the roles."""
    execute('install_contrail')
    #Clear the connections cache
    connections.clear()
    execute('setup_all')

def yum_install(rpms, disablerepo = False):
    if disablerepo:
        cmd = "yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail* install "
    else:
        cmd = "yum -y --nogpgcheck install "
    os_type = detect_ostype()
    # redhat platform installs from multiple repos
    if os_type in ['redhat']:
        cmd = "yum -y --nogpgcheck install "
    if os_type in ['centos', 'fedora', 'redhat', 'centoslinux']:
        for rpm in rpms:
            sudo(cmd + rpm)

def apt_install(debs):
    cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes --allow-unauthenticated install "
    if detect_ostype() in ['ubuntu']:
        for deb in debs:
            sudo(cmd + deb)

@task
def pkg_install(pkgs,disablerepo = False):
    if detect_ostype() in ['ubuntu']:
        apt_install(pkgs)
    elif detect_ostype() in ['centos', 'fedora', 'redhat', 'centoslinux']:
        yum_install(pkgs , disablerepo = disablerepo)

def pkg_cache_update():
    """ Update package metadata cache """
    if detect_ostype() in ['ubuntu']:
        sudo('DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes --allow-unauthenticated update')
    elif detect_ostype() in ['centos', 'fedora', 'redhat', 'centoslinux']:
        sudo('yum -y --nogpgcheck makecache')

@task
@parallel(pool_size=20)
@roles('compute')
def install_interface_name(reboot='True'):
    """Installs interface name package in all nodes defined in compute role."""
    if not env.roledefs['compute']:
        return
    execute("install_interface_name_node", env.host_string, reboot=reboot)

@task
def install_interface_name_node(*args, **kwargs):
    """Installs interface name package in one or list of nodes. USAGE:fab install_interface_name_node:user@1.1.1.1,user@2.2.2.2"""
    if detect_ostype() in ['ubuntu', 'redhat']:
        print "[%s]: Installing interface rename package not required for Ubuntu/Redhat..Skipping it" %env.host_string
        return
    if len(kwargs) == 0:
        reboot = 'True'
    else:
        reboot = kwargs['reboot']
    for host_string in args:
        with settings(host_string=host_string):
            rpm = ['contrail-interface-name']
            yum_install(rpm)
            if reboot == 'True':
                execute(reboot_node, 'yes', env.host_string)

@task
@EXECUTE_TASK
@roles('database')
def install_database(install_mongodb=True):
    """Installs database pkgs in all nodes defined in database."""
    if env.roledefs['database']:
        execute("install_database_node", install_mongodb, env.host_string)

@task
def install_database_node(install_mongodb, *args):
    """Installs database pkgs in one or list of nodes. USAGE:fab install_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-database']
            (dist, version, extra) = get_linux_distro()
            if dist.lower() == 'ubuntu' and version == '14.04':
                pkg = ['default-jre-headless'] + pkg
            if install_mongodb and is_ceilometer_install_supported(use_install_repo=True):
                pkgs_ceilometer_database = ['mongodb-clients', 'mongodb-server']
                pkg.extend(pkgs_ceilometer_database)
            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-database.override')
                apt_install(pkg)
            else:
                yum_install(pkg)

@task
@EXECUTE_TASK
@roles('compute')
def install_ceilometer_compute():
    """Installs ceilometer compute pkgs in all nodes defined in compute role."""
    if env.roledefs['compute']:
        execute("install_ceilometer_compute_node", env.host_string)

@task
def install_ceilometer_compute_node(*args):
    """Installs ceilometer compute pkgs in one or list of nodes. USAGE:fab install_ceilometer_compute_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            if not is_ceilometer_compute_install_supported():
                continue
            #Ceilometer not needed on vcenter ContraiVM
            if get_mode(env.host_string) == 'vcenter':
                continue
            pkgs = get_compute_ceilometer_pkgs()
            if pkgs:
                pkg_install(pkgs)
            else:
                act_os_type = detect_ostype()
                raise RuntimeError('Unspported OS type (%s)' % (act_os_type))

@task
@EXECUTE_TASK
@roles('openstack')
def install_contrail_ceilometer_plugin():
    """Installs contrail ceilometer plugin pkgs in all nodes of openstack role."""
    if env.roledefs['openstack']:
        execute("install_contrail_ceilometer_plugin_node", env.host_string)

@task
def install_contrail_ceilometer_plugin_node(*args):
    """Installs contrail ceilometer plugin pkgs in one or list of nodes.
       USAGE:fab install_contrail_ceilometer_plugin_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            if not is_ceilometer_contrail_plugin_install_supported():
                continue
            pkg_contrail_ceilometer = get_ceilometer_plugin_pkgs()
            act_os_type = detect_ostype()
            openstack_sku = get_openstack_sku()
            if not pkg_contrail_ceilometer:
                raise RuntimeError('Unsupported OpenStack distribution (%s) '
                    'on (%s)' % (openstack_sku, act_os_type))

            if act_os_type == 'ubuntu':
                apt_install(pkg_contrail_ceilometer)
            elif act_os_type in ['redhat']:
                # We need to copy the pkg from the cfgm node
                # and then install it on the openstack node
                cfgm_node = env.roledefs['cfgm'][0]
                if host_string != cfgm_node:
                    local_tempdir = tempfile.mkdtemp()
                    with lcd(local_tempdir):
                        for pkg in pkg_contrail_ceilometer:
                            with settings(host_string = cfgm_node):
                                get('/opt/contrail/contrail_install_repo/%s*.rpm' % (pkg), local_tempdir)
                    output = local("ls %s/*.rpm" % (local_tempdir), capture=True)
                    pkg_list = output.split('\n')
                    for pkg in pkg_list:
                        install_pkg_node(pkg, host_string)
                    local('rm -rf %s' % (local_tempdir))
                else:
                    yum_install(pkg_contrail_ceilometer)
            else:
                yum_install(pkg_contrail_ceilometer)

@task
@EXECUTE_TASK
@roles('openstack')
def install_ceilometer():
    """Installs ceilometer pkgs in all nodes defined in all nodes of openstack role."""
    if env.roledefs['openstack']:
        execute("install_ceilometer_node", env.host_string)

@task
def install_ceilometer_node(*args):
    """Installs openstack pkgs in one or list of nodes. USAGE:fab install_ceilometer_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            if not is_ceilometer_install_supported():
                continue
            pkg_ceilometer = get_openstack_ceilometer_pkgs()
            act_os_type = detect_ostype()
            openstack_sku = get_openstack_sku()
            if not pkg_ceilometer:
                raise RuntimeError('Unsupported OpenStack distribution (%s) '
                    'on (%s)' % (openstack_sku, act_os_type))
            if act_os_type == 'ubuntu':
                apt_install(pkg_ceilometer)
            elif act_os_type in ['redhat']:
                # We need to copy the pkg from the cfgm node
                # and then install it on the openstack node
                cfgm_node = env.roledefs['cfgm'][0]
                local_tempdir = tempfile.mkdtemp()
                with lcd(local_tempdir):
                    for pkg in pkg_ceilometer:
                        with settings(host_string = cfgm_node):
                            get('/opt/contrail/contrail_install_repo/%s*.rpm' % (pkg), local_tempdir)
                output = local("ls %s/*.rpm" % (local_tempdir), capture=True)
                pkg_list = output.split('\n')
                for pkg in pkg_list:
                    install_pkg_node(pkg, host_string)
                local('rm -rf %s' % (local_tempdir))
            else:
                yum_install(pkg_ceilometer)

@task
@EXECUTE_TASK
@roles('openstack')
def install_openstack():
    """Installs openstack pkgs in all nodes defined in openstack role."""
    if env.roledefs['openstack']:
        execute("install_openstack_node", env.host_string)
        execute('add_reserved_ports_node', '35357,35358,33306,9322', env.host_string)

@task
def install_openstack_node(*args):
    """Installs openstack pkgs in one or list of nodes. USAGE:fab install_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkgs = get_openstack_pkgs()
            if detect_ostype() == 'ubuntu':
                apt_install(pkgs)
            else:
                yum_install(pkgs)
            install_ceilometer_node(host_string)

@task
@EXECUTE_TASK
@roles('cfgm')
def install_cfgm():
    """Installs config pkgs in all nodes defined in cfgm role."""
    if env.roledefs['cfgm']:
        execute("install_cfgm_node", env.host_string)

@task
def install_cfgm_node(*args):
    """Installs config pkgs in one or list of nodes. USAGE:fab install_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = get_config_pkgs()

            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-config.override')
                sudo('echo "manual" >> /etc/init/neutron-server.override')
                apt_install(pkg)
            else:
                yum_install(pkg)

            if get_orchestrator() is 'vcenter':
                pkg = get_vcenter_plugin_pkg()
                install_contrail_vcenter_plugin(pkg)

@task
@EXECUTE_TASK
@roles('control')
def install_control():
    """Installs control pkgs in all nodes defined in control role."""
    if env.roledefs['control']:
        execute("install_control_node", env.host_string)

@task
def install_control_node(*args):
    """Installs control pkgs in one or list of nodes. USAGE:fab install_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-control']
            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-control.override')
                    sudo('echo "manual" >> /etc/init/supervisor-dns.override')
                apt_install(pkg)
            else:
                yum_install(pkg)


@task
@EXECUTE_TASK
@roles('collector')
def install_collector():
    """Installs analytics pkgs in all nodes defined in collector role."""
    if env.roledefs['collector']:
        execute("install_collector_node", env.host_string)

@task
def install_collector_node(*args):
    """Installs analytics pkgs in one or list of nodes. USAGE:fab install_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-analytics', 'contrail-docs']
            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-analytics.override')
                apt_install(pkg)
            else:
                yum_install(pkg)


@task
@EXECUTE_TASK
@roles('webui')
def install_webui():
    """Installs webui pkgs in all nodes defined in webui role."""
    if env.roledefs['webui']:
        execute("install_webui_node", env.host_string)

@task
def install_webui_node(*args):
    """Installs webui pkgs in one or list of nodes. USAGE:fab install_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-webui']
            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-webui.override')
                apt_install(pkg)
            else:
                yum_install(pkg)

@task
@EXECUTE_TASK
@roles('vcenter_compute')
def install_vcenter_compute():
    """Installs nova compute in all nodes defined in vcenter_compute role."""
    if 'vcenter_compute' in env.roledefs:
       execute("install_vcenter_compute_node", env.host_string)

@task
def install_vcenter_compute_node(*args):
    """Installs nova compute in all nodes defined in vcenter_compute role."""
    for host_string in args:
        with  settings(host_string=host_string):
              ostype = detect_ostype()
              pkgs = get_vcenter_compute_pkgs()

              if ostype == 'ubuntu':
                 apt_install(pkgs)
              else:
                 yum_install(pkgs)

              if 'vcenter_compute' in env.roledefs:
                 pkg = get_vcenter_plugin_pkg()
                 install_contrail_vcenter_plugin(pkg)

@task
@EXECUTE_TASK
@roles('compute')
def install_vrouter(manage_nova_compute='yes'):
    """Installs vrouter pkgs in all nodes defined in vrouter role."""
    if env.roledefs['compute']:
        # Nova compute need not required for TSN node
        if 'tsn' in env.roledefs.keys():
            if  env.host_string in env.roledefs['tsn']: manage_nova_compute='no'
        if get_mode(env.host_string) is 'vcenter': 
            manage_nova_compute='no'
        execute("install_only_vrouter_node", manage_nova_compute, env.host_string)

@task
def install_vrouter_node(*args):
    """Installs nova compute and vrouter pkgs in one or list of nodes. USAGE:fab install_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            if get_mode(host_string) is 'vcenter':
                execute('install_only_vrouter_node', 'no', host_string)
            else:
                execute('install_only_vrouter_node', 'yes', host_string)

@task
def install_only_vrouter_node(manage_nova_compute='yes', *args):
    """Installs only vrouter pkgs in one or list of nodes. USAGE:fab install_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no, User has to install nova-compute in the compute node.
    """
    for host_string in args:
        with  settings(host_string=host_string):
            pkgs = get_compute_pkgs(manage_nova_compute)

            if detect_ostype() == 'ubuntu':
                if not is_xenial_or_above():
                    sudo('echo "manual" >> /etc/init/supervisor-vrouter.override')
                apt_install(pkgs)
            else:
                yum_install(pkgs)
            install_ceilometer_compute_node(host_string)

@task
@EXECUTE_TASK
@roles('all')
def install_net_driver():
    """Installs network drives that are packaged with contrail
    """
    execute("install_net_driver_node", env.host_string)

@task
def install_net_driver_node(*args):
    """Installs network drives that are packaged with contrail
       on a single node. Called during a add_vrouter_node
    """
    for host_string in args:
        with  settings(host_string=host_string):
            ostype = detect_ostype()
            pkgs = get_net_driver_pkgs()

            if get_orchestrator() is not 'vcenter':
                if ostype == 'ubuntu':
                    apt_install(pkgs)
                    # Update initrd to add the new drivers
                    # if necessary.
                    sudo('update-initramfs -k all -u')

@task
@EXECUTE_TASK
@roles('all')
def create_installer_repo():
    """Execute setup.sh corresponding to contrail-installer-packages in
       all nodes
    """
    execute("create_installer_repo_node", env.host_string)

@task
def create_installer_repo_node(*args):
    """Execute setup.sh corresponding to contrail-installer-packages"""
    for host_string in args:
        with settings(host_string=host_string):
            if exists('/opt/contrail/contrail_installer_packages/setup.sh', use_sudo=True):
                sudo('/opt/contrail/contrail_installer_packages/setup.sh')

@task
@EXECUTE_TASK
@roles('all')
def create_install_repo(*tgzs, **kwargs):
    """Creates contrail install repo in all nodes."""
    if len(tgzs) == 0:
        execute("create_install_repo_node", env.host_string)
    else:
        execute("create_install_repo_from_tgz_node", env.host_string, *tgzs, **kwargs)

@task
@roles('build')
def create_install_repo_without_openstack(*tgzs, **kwargs):
    """Creates contrail install repo in all nodes excluding openstack node."""
    for host_string in env.roledefs['all']:
        if host_string in env.roledefs['openstack']:
            continue
        with settings(host_string=host_string):
            if len(tgzs) == 0:
                execute('create_install_repo_node', host_string)
            else:
                execute('create_install_repo_from_tgz_node', host_string, *tgzs, **kwargs)

@task
@roles('build')
def create_install_repo_without_openstack_and_compute(*tgzs, **kwargs):
    """Creates contrail install repo in all nodes excluding openstack and compute nodes."""
    if len(tgzs) == 0:
        cmd = 'create_install_repo_node'
    else:
        cmd = 'create_install_repo_from_tgz_node'

    for host_string in env.roledefs['all']:
        if host_string in env.roledefs['openstack'] or host_string in env.roledefs['compute']:
            continue
        with settings(host_string=host_string):
            execute(cmd, host_string, *tgzs, **kwargs)

@task
def create_install_repo_from_tgz_node(host_string, *tgzs, **kwargs):
    """Create contrail repos from each tgz files in the given node
       * tgzs can be absolute/relative paths or a pattern
    """
    # verify tgz's availability
    cant_use = []
    usable_tgz_files = []
    for tgz in tgzs:
        tgz_files = os.path.abspath(os.path.expanduser(tgz))
        tgz_file_list = glob.glob(tgz_files)
        for tgz_file in tgz_file_list:
            if not os.access(tgz_file, os.R_OK):
                cant_use.append(tgz_file)
            elif not tarfile.is_tarfile(tgz_file):
                cant_use.append(tgz_file)
            else:
                usable_tgz_files.append(tgz_file)

    if len(cant_use) != 0:
        print "ERROR: TGZ file mentioned below are not readable or", \
              "not a valid tgz file or do not exists"
        print "\n".join(cant_use)

    for tgz in usable_tgz_files:
        with settings(host_string=host_string, warn_only=True):
            os_type = detect_ostype()
        if os_type in ['centos', 'fedora', 'redhat', 'centoslinux']:
            execute(create_yum_repo_from_tgz_node, tgz, host_string, **kwargs)
        elif os_type in ['ubuntu']:
            execute(create_apt_repo_from_tgz_node, tgz, host_string, **kwargs)

@task
def create_install_repo_node(*args):
    """Creates contrail install repo in one or list of nodes. USAGE:fab create_install_repo_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            os_type = detect_ostype()
            install_versions = get_pkg_version_release('contrail-install-packages')
            # If contrail-install-packages is not installed, cant continue as setup.sh
            # wont be present
            if not install_versions:
                print 'WARNING: contrail-install-packages is not installed, Skipping!!!'
                return
            if os_type in ['centos', 'redhat', 'centoslinux', 'fedora']:
                install_versions = ['.'.join([install_version.split('~')[0], install_version.split('~')[1].split('.')[1]]) \
                                for install_version in install_versions]
            elif os_type in ['ubuntu']:
                install_versions = [install_version.split('~')[0] for install_version in install_versions]
            else:
                raise RuntimeError('UnSupported os type (%s)' % os_type)

            contrail_setup_versions = get_available_packages(os_type, 'contrail-setup')
            setup_versions = [version.strip('.centos') for version in contrail_setup_versions['contrail-setup']]

            # If one of the available versions of contrail-setup packages matches
            # with the installed version of contrail-install-packages, then its safer to
            # assume that the corresponding local repo was already created

            if install_versions[0] not in setup_versions:
                if exists('/opt/contrail/contrail_packages/setup.sh', use_sudo=True):
                    sudo("sudo /opt/contrail/contrail_packages/setup.sh")
                else:
                    raise RuntimeError('/opt/contrail/contrail_packages/setup.sh is not available')

@roles('build')
@task
def install_orchestrator():
    if get_orchestrator() is 'openstack':
        execute(install_openstack)
        execute(update_keystone_log)

@task
@EXECUTE_TASK
@roles('all')
def get_package_installation_time(os_type, package):
    '''Retrieve given package's installation time with its version
       Incase of kernel package, old kernel package will still show up in
       the installed packages list and will return installation time of all
       versions
    '''
    pkg_versions_list = []
    if os_type in ['ubuntu']:
        cmd = "cd /var/lib/dpkg/info && find . -type f -name \"%s\.list\" " \
              "-exec sh -c \'pkg=$(echo \"$0\" | sed -e \"s|\./\(.*\)\.list|\\1|g\"); " \
              "echo $(stat -c \"%%Y\" \"$0\") $(dpkg-query -W -f=\"\\\${Version}\\n\" \"$pkg\")\' {} \;" % package
    elif os_type in ['centos', 'redhat', 'fedora', 'centoslinux']:
        cmd = "rpm -q --queryformat='%%{installtime} " \
              "%%{VERSION}-%%{RELEASE}.%%{ARCH}\\n' %s" % package
    else:
        print '[%s]: WARNING: Unsupported OS type (%s)' % (env.host_string, os_type)

    pkg_versions = sudo(cmd)
    for version_info in pkg_versions.split('\r\n'):
        installed_time, version = version_info.split()
        pkg_versions_list.append((int(installed_time), version))

    # rearrange package version based on its installation time
    pkg_versions_list.sort(key=lambda x: x[0])
    return pkg_versions_list

@task
@roles('build')
def reboot_on_kernel_update_without_openstack(reboot='True'):
    '''When kernel package is upgraded as a part of any depends,
       system needs to be rebooted so new kernel is effective
    '''
    all_nodes = env.roledefs['all']
    # remove openstack node
    for nodename in env.roledefs['openstack']:
        if nodename in all_nodes:
            all_nodes.remove(nodename)

    # moving current node to last to reboot current node at last
    if env.roledefs['build'] in all_nodes:
        all_nodes.remove(env.roledefs['build']).append(env.roledefs['build'])
    with settings(host_string=env.roledefs['cfgm'][0]):
        os_type = detect_ostype()
    if os_type in ['ubuntu']:
        nodes_version_info_act = execute('get_package_installation_time', os_type,
                                         '*linux-image-[0-9]*-generic')
        # replace minor version with '-generic'
        nodes_version_info = {}
        for key, values in nodes_version_info_act.items():
            nodes_version_info[key] = [(index0, ".".join(index1.split('.')[:-1]) + '-generic') \
                                       for index0, index1 in values]
    elif os_type in ['centos', 'redhat', 'fedora', 'centoslinux']:
        nodes_version_info = execute('get_package_installation_time', os_type, 'kernel')
    else:
        print '[%s]: WARNING: Unsupported OS type (%s)' % (env.host_string, os_type)

    for node in all_nodes:
        with settings(host_string=node):
            uname_out = sudo('uname -r')
            if node in nodes_version_info.keys():
                versions_info = nodes_version_info[node]
                # skip reboot if latest kernel version is same as
                # current kernel version in the node
                if uname_out != versions_info[-1][1]:
                    print '[%s]: Node is booted with old kernel, Reboot required' % node
                    if reboot == 'True':
                        execute(reboot_nodes, node)
                    else:
                        print '[%s]: WARNING:: Reboot is skipped as Reboot=False is set. ' \
                              'Reboot manually before setup to avoid misconfiguration!' % node
                else:
                    print '[%s]: Node is already booted with new kernel' % node

@task
@roles('build')
def reboot_on_kernel_update(reboot='True'):
    '''When kernel package is upgraded as a part of any depends,
       system needs to be rebooted so new kernel is effective
    '''
    all_nodes = env.roledefs['all']
    # moving current node to last to reboot current node at last
    if env.roledefs['build'] in all_nodes:
        all_nodes.remove(env.roledefs['build']).append(env.roledefs['build'])
    with settings(host_string=env.roledefs['cfgm'][0]):
        os_type = detect_ostype()
    if os_type in ['ubuntu']:
        nodes_version_info_act = execute('get_package_installation_time', os_type,
                                         '*linux-image-[0-9]*-generic')
        # replace minor version with '-generic'
        nodes_version_info = {}
        for key, values in nodes_version_info_act.items():
            nodes_version_info[key] = [(index0, ".".join(index1.split('.')[:-1]) + '-generic') \
                                       for index0, index1 in values]
    elif os_type in ['centos', 'redhat', 'fedora', 'centoslinux']:
        nodes_version_info = execute('get_package_installation_time', os_type, 'kernel')
    else:
        print '[%s]: WARNING: Unsupported OS type (%s)' % (env.host_string, os_type)

    for node in all_nodes:
        with settings(host_string=node):
            uname_out = sudo('uname -r')
            if node in nodes_version_info.keys():
                versions_info = nodes_version_info[node]
                # skip reboot if latest kernel version is same as
                # current kernel version in the node
                if uname_out != versions_info[-1][1]:
                    print '[%s]: Node is booted with old kernel, Reboot required' % node
                    if reboot == 'True':
                        execute(reboot_nodes, node)
                    else:
                        print '[%s]: WARNING:: Reboot is skipped as Reboot=False is set. ' \
                              'Reboot manually before setup to avoid misconfiguration!' % node
                else:
                    print '[%s]: Node is already booted with new kernel' % node


@roles('build')
@task
def install_new_contrail(**kwargs):
    """Installs required contrail packages in all nodes as per the role definition.
    """
    new_host = kwargs.get('new_ctrl')
    execute('pre_check')
    execute(create_install_repo_node, new_host)

    if new_host in env.roledefs['database']:
        execute(install_database_node, True, new_host)
    if (get_orchestrator() is 'openstack'):
        if new_host in env.roledefs['openstack']:
            execute("install_openstack_node", new_host)
    else:
        print "ERROR: Only adding a new Openstack controller is supported"
        return

    if new_host in env.roledefs['cfgm']:
        execute(install_cfgm_node, new_host)

    if new_host in env.roledefs['control']:
        execute(install_control_node, new_host)

    if new_host in env.roledefs['collector']:
        execute(install_collector_node, new_host)

    if new_host in env.roledefs['webui']:
        execute(install_webui_node, new_host)


@roles('build')
@task
def install_contrail(*tgzs, **kwargs):
    """Installs required contrail packages in all nodes as per the role definition.
       tgzs: List of TGZ files or pattern; Supply tgzs when using TGZs for installation
       kwargs:
           reboot: True/False; True - To reboot nodes if interface rename is applied and on kernel upgrade
                               Default: True
           extra_repo: yes/no; yes - Extract repos recursively from given TGZs.
                               Default: no
    """
    reboot = kwargs.get('reboot', 'True')
    execute('pre_check')
    execute('create_installer_repo')
    execute(create_install_repo, *tgzs, **kwargs)
    execute(install_database)
    execute('install_orchestrator')
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    if 'vcenter_compute' in env.roledefs:
        execute(install_vcenter_compute)
    execute(install_vrouter)
    execute(install_net_driver)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name, reboot)
        #Clear the connections cache
        connections.clear()
    execute('reboot_on_kernel_update', reboot)

@roles('build')
@task
def install_without_openstack(*tgzs, **kwargs):
    """Installs required contrail packages in all nodes as per the role definition except the openstack.
       User has to install the openstack node with their custom openstack pakckages.
       tgzs: List of TGZ files or pattern; Supply tgzs when using TGZs for installation
       kwargs:
           manage_nova_compute: no/yes; no - User has to install nova-compute in compute nodes
                                Default: yes
           install_vrouter: no/yes; no - Vrouter and its dependent packages will be skipped in compute nodes
                                Default: yes
           reboot: True/False; True - To reboot nodes if interface rename is applied and on kernel upgrade
                               Default: True
           extra_repo: yes/no; yes - Extract repos recursively from given TGZs.
                               Default: no
    """
    manage_nova_compute = kwargs.get('manage_nova_compute', 'yes')
    install_vrouter = kwargs.get('install_vrouter', 'yes')
    reboot = kwargs.get('reboot', 'True')
    execute('create_installer_repo')
    execute(create_install_repo_without_openstack, *tgzs, **kwargs)
    execute(install_database, False)
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    if install_vrouter == 'yes':
        execute('install_vrouter', manage_nova_compute)
    execute(install_net_driver)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name, reboot)
    execute('reboot_on_kernel_update_without_openstack', reboot)

@roles('build')
@task
def install_without_openstack_and_compute(*tgzs, **kwargs):
    """ Installs contrail package without openstack and compute. Typically used for ISSU."""
    execute('create_installer_repo')
    execute(create_install_repo_without_openstack_and_compute, *tgzs, **kwargs)
    execute('pre_check')
    execute(install_database, False)
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)

@roles('build')
@task
def install_contrail_analytics_components(*tgzs, **kwargs):
    """Installs required contrail packages in all nodes as per the role definition.
       this task is used to install non-networking contrail components - config,
       analytics, database and webui
       tgzs: List of TGZ files or pattern; Supply tgzs when using TGZs for installation
       kwargs:
           manage_nova_compute: no/yes; no - User has to install nova-compute in compute nodes
                                Default: yes
           reboot: True/False; True - To reboot nodes if interface rename is applied and on kernel upgrade
                               Default: True
           extra_repo: yes/no; yes - Extract repos recursively from given TGZs.
                               Default: no
    """
    manage_nova_compute = kwargs.get('manage_nova_compute', 'no')
    reboot = kwargs.get('reboot', 'False')
    execute('create_installer_repo')
    execute(create_install_repo_without_openstack, *tgzs, **kwargs)
    execute(install_database, False)
    execute(install_cfgm)
    execute(install_collector)
    execute(install_webui)

@roles('openstack')
@task
def update_keystone_log():
    """Temporary workaround to update keystone log"""
    #TODO This is a workaround. Need to be fixed as part of package install
    if detect_ostype() in ['ubuntu']:
        with  settings(warn_only=True):
            sudo("touch /var/log/keystone/keystone.log")
            sudo("sudo chown keystone /var/log/keystone/keystone.log")
            sudo("sudo chgrp keystone /var/log/keystone/keystone.log")


@roles('build')
@task
def copy_install_pkgs(pkgs):
     try:
         pkg_dir = env.pkg_dir
     except:
         pkg_dir = None

     if pkg_dir == None:
         all_pkgs = pkgs.split()
     else:
         all_pkgs = []
         for pkg in pkgs.split():
             all_pkgs.extend(glob.glob('%s/%s' %(pkg_dir, pkg)))

     for pkg in all_pkgs:
         tgt_hosts = []
         if re.match('.*contrail-api', pkg):
             tgt_hosts = env.roledefs['cfgm']
         elif re.match('.*contrail-control', pkg):
             tgt_hosts = env.roledefs['control']
         elif re.match('.*contrail-agent', pkg):
             tgt_hosts = env.roledefs['compute']
         elif re.match('.*contrail-analytics', pkg):
             tgt_hosts = env.roledefs['collector']
         elif re.match('.*contrail-setup', pkg):
             tgt_hosts = env.roledefs['all']

         for tgt_host in tgt_hosts:
             copy_pkg(tgt_host, pkg)
             install_pkg(tgt_host, pkg)
#end copy_install_pkgs

@roles('cfgm')
@task
def install_webui_packages(source_dir):
    webui = getattr(testbed, 'ui_browser', False)
    if detect_ostype() in ['ubuntu']:
        sudo('cp ' + source_dir + '/contrail-test/scripts/ubuntu_repo/sources.list /etc/apt')
        sudo('sudo apt-get -y update')
        sudo('sudo apt-get install -y xvfb')
        if webui == 'firefox':
            sudo('sudo apt-get install -y firefox')
            sudo('sudo apt-get remove -y firefox')
            sudo('wget https://ftp.mozilla.org/pub/mozilla.org/firefox/releases/31.0/linux-x86_64/en-US/firefox-31.0.tar.bz2')
            sudo('tar -xjvf firefox-31.0.tar.bz2')
            sudo('sudo mv firefox /opt/firefox')
            sudo('sudo ln -sf /opt/firefox/firefox /usr/bin/firefox')
        elif webui == 'chrome':
            sudo('echo "deb http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee -a /etc/apt/sources.list')
            sudo('wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -')
            sudo('sudo apt-get -y update')
            sudo('sudo apt-get -y install unzip')
            sudo('wget -c http://chromedriver.storage.googleapis.com/2.10/chromedriver_linux64.zip')
            sudo('unzip chromedriver_linux64.zip')
            sudo('sudo cp ./chromedriver /usr/bin/')
            sudo('sudo chmod ugo+rx /usr/bin/chromedriver')
            sudo('sudo apt-get -y install libxpm4 libxrender1 libgtk2.0-0 libnss3 libgconf-2-4')
            sudo('sudo apt-get -y install google-chrome-stable')
    elif detect_ostype() in ['centos', 'fedora', 'redhat', 'centoslinux']:
        sudo('yum install -y xorg-x11-server-Xvfb')
        sudo('wget http://ftp.mozilla.org/pub/mozilla.org/firefox/releases/33.0/linux-x86_64/en-US/firefox-33.0.tar.bz2')
        sudo('tar -xjvf firefox-33.0.tar.bz2')
        sudo('sudo mv firefox /opt/firefox')
        sudo('sudo ln -sf /opt/firefox/firefox /usr/bin/firefox')
#end install_webui_packages


@roles('rally')
@task
def install_rally():
    """install rally"""
    if env.roledefs['rally']:
        execute(pkg_cache_update)
        install_rally='wget -q -O /tmp/install_rally.sh https://raw.githubusercontent.com/openstack/rally/master/install_rally.sh && bash /tmp/install_rally.sh -y '

        if testbed.rally_git_url:
            install_rally += ' --url ' + testbed.rally_git_url

        if testbed.rally_git_branch:
            install_rally += ' --branch ' + testbed.rally_git_branch

        sudo(install_rally)
#end install_rally

@task
def update_config_option(role, file_path, section, option, value, service, sku):
    """Task to update config option of any section in a conf file
       USAGE:fab update_config_option:openstack,/etc/keystone/keystone.conf,token,expiration,86400,keystone
    """
    cmd1 = "openstack-config --set " + file_path + " " +  section + " " + option + " " + value
    for host in env.roledefs[role]:
        with settings(host_string=host, password=get_env_passwords(host)):
            ostype = detect_ostype()
            service_name = SERVICE_NAMES.get(service, {}).get(ostype, service)
            cmd2 = "service " + service_name + " restart"
            if service == 'keystone':
                if sku == 'newton':
                    cmd2 = '/etc/init.d/apache2 restart'
                elif sku == 'ocata':
                    cmd1 = "sed -i 's/\[token\]/\[token\]\\nexpiration=86400/' \
                           /etc/kolla/keystone/keystone.conf < /etc/kolla/keystone/keystone.conf"
                    cmd2 = 'docker restart ' + service_name
                    cmd = "docker exec -it horizon "
                    sudo_usr_path = "sudo /usr/share/openstack-dashboard/manage.py "
                    cmd3 = cmd + "sudo sed -i -e\
                                 's:/usr/share/openstack-dashboard/static:\
                                 /var/lib/openstack-dashboard/static:g' \
                                 /etc/apache2/conf-enabled/000-default.conf "
                    cmd4 = cmd + sudo_usr_path + " collectstatic --noinput"
                    cmd5 = cmd + sudo_usr_path + " compress"
                    cmd6 = cmd + "service apache2 reload"
                    sudo(cmd3)
                    sudo(cmd4)
                    sudo(cmd5)
                    sudo(cmd6)
            sudo(cmd1)
            sudo(cmd2)
# end update_config_option

@task
def update_js_config(role, file_path, service, container=None):
    """Task to update config of any section in a js file
       USAGE:fab update_js_config:openstack,/etc/contrail/config.global.js,contrail-webui
    """
    if container:
       cmd = "docker exec -it controller bash "
       cmd1 = cmd + "-c \"echo config.session = \{\}\; >> "  + file_path + "\""
       cmd2 = cmd + "-c \"echo config.session.timeout = 86400 \* 1000\; >> " + file_path + "\""
       cmd3 = cmd + "service " + service + " restart"
    else:
       cmd1 = "echo 'config.session = {};' >> " + file_path
       cmd2 = "echo 'config.session.timeout = 86400 * 1000;' >> " + file_path
       cmd3 = "service " + service + " restart"
    for host in env.roledefs[role]:
        with settings(host_string=host, password=get_env_passwords(host)):
            sudo(cmd1)
            sudo(cmd2)
            sudo(cmd3)
# end update_js_config

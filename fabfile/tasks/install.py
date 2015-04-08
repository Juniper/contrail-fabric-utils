import os
import re
import copy
import time
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.cluster import is_lbaas_enabled, get_orchestrator,\
     reboot_nodes
from fabfile.utils.host import get_from_testbed_dict,\
    get_openstack_internal_vip, get_hypervisor, get_env_passwords
from fabfile.tasks.helpers import reboot_node
from fabfile.utils.analytics import is_ceilometer_install_supported, \
    is_ceilometer_compute_install_supported

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
@parallel(pool_size=20)
@roles('cfgm')
def install_contrail_vcenter_plugin(pkg):
    """Installs any rpm/deb package in all nodes."""
    execute('install_pkg_node', pkg, env.host_string)
    execute('install_contrail_vcenter_plugin_node', env.host_string)

@task
def install_contrail_vcenter_plugin_node( *args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo('cd /opt/contrail/contrail_vcenter_plugin_install_repo/; dpkg -i *')

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

@task
@EXECUTE_TASK
@roles('all')
def upgrade_pkgs():
    """Upgrades the pramiko and pycrypto packages in all nodes."""
    execute("upgrade_pkgs_node", env.host_string)

@task
@roles('build')
def upgrade_pkgs_without_openstack():
    """Upgrades the pramiko and pycrypto packages in all nodes excluding openstack node."""
    host_strings = copy.deepcopy(env.roledefs['all'])
    dummy = [host_strings.remove(openstack_node)
             for openstack_node in env.roledefs['openstack']]
    for host_string in host_strings:
        with settings(host_string=host_string):
            execute("upgrade_pkgs_node", host_string)

@task
def upgrade_pkgs_node(*args):
    """Upgrades the pramiko/pcrypto packages in single or list of nodes. USAGE:fab upgrade_pkgs_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            # This step is required in customer env, becasue they used to call fab
            # commands from one of the node in the cluster(cfgm).
            # Installing packages(python-nova, python-cinder) brings in lower version
            # of python-paramiko(1.7.5), fabric-utils requires 1.9.0 or above.
            # ubuntu does not need this, as pycrypto and paramiko are installed as debian packages.
            cmd = "sudo easy_install \
                  /opt/contrail/python_packages/pycrypto-2.6.tar.gz;\
                  sudo easy_install \
                  /opt/contrail/python_packages/paramiko-1.11.0.tar.gz"
            if detect_ostype() in ['centos', 'fedora', 'redhat']:
                sudo(cmd)

def yum_install(rpms, disablerepo = True):
    if disablerepo:
        cmd = "yum -y --nogpgcheck --disablerepo=* --enablerepo=contrail_install_repo install "
    else:
        cmd = "yum -y --nogpgcheck install "
    os_type = detect_ostype()
    # redhat platform installs from multiple repos
    if os_type in ['redhat']:
        cmd = "yum -y --nogpgcheck install "
    if os_type in ['centos', 'fedora', 'redhat']:
        for rpm in rpms:
            sudo(cmd + rpm)

def apt_install(debs):
    cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes --allow-unauthenticated install "
    if detect_ostype() in ['ubuntu']:
        for deb in debs:
            sudo(cmd + deb)

def pkg_install(pkgs,disablerepo = True):
    if detect_ostype() in ['ubuntu']:
        apt_install(pkgs)
    elif detect_ostype() in ['centos', 'fedora', 'redhat']:
        yum_install(pkgs , disablerepo = disablerepo)

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
def install_database():
    """Installs database pkgs in all nodes defined in database."""
    if env.roledefs['database']:
        execute("install_database_node", env.host_string)

@task
def install_database_node(*args):
    """Installs database pkgs in one or list of nodes. USAGE:fab install_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-database']
            if detect_ostype() == 'ubuntu':
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
            pkg_ubuntu = ['ceilometer-agent-compute']
            pkg_redhat = ['openstack-ceilometer-compute']
            act_os_type = detect_ostype()
            if act_os_type == 'ubuntu':
                apt_install(pkg_ubuntu)
            elif act_os_type in ['redhat']:
                yum_install(pkg_redhat)
            else:
                raise RuntimeError('Unspported OS type (%s)' % (act_os_type))

@task
@EXECUTE_TASK
@roles('openstack')
def install_contrail_ceilometer_plugin():
    """Installs contrail ceilometer plugin pkgs in the first node of openstack role."""
    execute("install_contrail_ceilometer_plugin_node", env.host_string)

@task
def install_contrail_ceilometer_plugin_node(*args):
    """Installs contrail ceilometer plugin pkgs in one or list of nodes.
       USAGE:fab install_contrail_ceilometer_plugin_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        if env.roledefs['openstack'] and \
                host_string != env.roledefs['openstack'][0]:
            continue
        with settings(host_string=host_string):
            if not is_ceilometer_install_supported():
                continue
            pkg_contrail_ceilometer = ['ceilometer-plugin-contrail']
            act_os_type = detect_ostype()
            openstack_sku = get_openstack_sku()
            if openstack_sku == 'icehouse':
                if not act_os_type in ['ubuntu', 'redhat']:
                    raise RuntimeError('Unsupported OpenStack distribution '
                        '(%s) on OS type (%s)' % (openstack_sku, act_os_type))
            elif openstack_sku == 'juno':
                if not act_os_type in ['ubuntu']:
                    raise RuntimeError('Unsupported OpenStack distribution '
                        '(%s) on OS type (%s)' % (openstack_sku, act_os_type))
            else:
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
    """Installs ceilometer pkgs in all nodes defined in first node of openstack role."""
    execute("install_ceilometer_node", env.host_string)

@task
def install_ceilometer_node(*args):
    """Installs openstack pkgs in one or list of nodes. USAGE:fab install_ceilometer_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        if env.roledefs['openstack'] and \
                host_string != env.roledefs['openstack'][0]:
            continue
        with settings(host_string=host_string):
            if not is_ceilometer_install_supported():
                continue
            pkg_havana_ubuntu = ['mongodb', 'ceilometer-api',
                'ceilometer-collector',
                'ceilometer-agent-central',
                'python-ceilometerclient']
            pkg_icehouse_ubuntu = ['mongodb', 'ceilometer-api',
                'ceilometer-collector',
        	'ceilometer-agent-central',
        	'ceilometer-agent-notification',
        	'ceilometer-alarm-evaluator',
        	'ceilometer-alarm-notifier',
		'python-ceilometerclient',
                'ceilometer-plugin-contrail']
            pkg_juno_ubuntu = ['mongodb-server', 'mongodb-clients',
                'python-pymongo', 'ceilometer-api',
                'ceilometer-collector',
                'ceilometer-agent-central',
                'ceilometer-agent-notification',
                'ceilometer-alarm-evaluator',
                'ceilometer-alarm-notifier',
                'python-ceilometerclient',
                'ceilometer-plugin-contrail']
            pkg_icehouse_redhat = ['ceilometer-plugin-contrail']
            act_os_type = detect_ostype()
            openstack_sku = get_openstack_sku()
            if openstack_sku == 'havana':
                if act_os_type == 'ubuntu':
                    pkg_ceilometer = pkg_havana_ubuntu
                else:
                    raise RuntimeError('Unsupported OpenStack distribution '
                        '(%s) on OS type (%s)' % (openstack_sku, act_os_type))
            elif openstack_sku == 'icehouse':
                if act_os_type == 'ubuntu':
                    pkg_ceilometer = pkg_icehouse_ubuntu
                elif act_os_type in ['redhat']:
                    pkg_ceilometer = pkg_icehouse_redhat
                else:
                    raise RuntimeError('Unsupported OpenStack distribution '
                        '(%s) on OS type (%s)' % (openstack_sku, act_os_type))
            elif openstack_sku == 'juno':
                if act_os_type == 'ubuntu':
                    pkg_ceilometer = pkg_juno_ubuntu
                else:
                    raise RuntimeError('Unsupported OpenStack distribution '
                        '(%s) on OS type (%s)' % (openstack_sku, act_os_type))
            else:
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

@task
def install_openstack_node(*args):
    """Installs openstack pkgs in one or list of nodes. USAGE:fab install_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack']
            if len(env.roledefs['openstack']) > 1 and get_openstack_internal_vip():
                pkg.append('contrail-openstack-ha')
            if detect_ostype() == 'ubuntu':
                apt_install(pkg)
            else:
                yum_install(pkg)
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
            pkg = ['contrail-openstack-config']
            if detect_ostype() == 'ubuntu':
                sudo('echo "manual" >> /etc/init/supervisor-config.override')
                sudo('echo "manual" >> /etc/init/neutron-server.override')
                apt_install(pkg)
            else:
                yum_install(pkg)


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
            pkg = ['contrail-openstack-analytics']
            if detect_ostype() == 'ubuntu':
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
                sudo('echo "manual" >> /etc/init/supervisor-webui.override')
                apt_install(pkg)
            else:
                yum_install(pkg)


@task
@EXECUTE_TASK
@roles('compute')
def install_vrouter(manage_nova_compute='yes'):
    """Installs vrouter pkgs in all nodes defined in vrouter role."""
    if env.roledefs['compute']:
        # Nova compute need not required for TSN node
        if 'tsn' in env.roledefs.keys():
            if  env.host_string in env.roledefs['tsn']: manage_nova_compute='no'
        if get_orchestrator() is 'vcenter': manage_nova_compute='no'
        execute("install_only_vrouter_node", manage_nova_compute, env.host_string)

@task
def install_vrouter_node(*args):
    """Installs nova compute and vrouter pkgs in one or list of nodes. USAGE:fab install_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute('install_only_vrouter_node', 'yes', *args)

@task
def install_only_vrouter_node(manage_nova_compute='yes', *args):
    """Installs only vrouter pkgs in one or list of nodes. USAGE:fab install_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no, User has to install nova-compute in the compute node.
    """
    for host_string in args:
        with  settings(host_string=host_string):
            ostype = detect_ostype()
            pkg = ['contrail-openstack-vrouter']

            # For Ubuntu, Install contrail-vrouter-generic package if one available for
            # node's kernel version or install contrail-vrouter-dkms
            # If dkms is already installed, continue to upgrade contrail-vrouter-dkms
            if ostype in ['ubuntu']:
                dkms_status = get_build('contrail-vrouter-dkms')
                if dkms_status is not None:
                    contrail_vrouter_pkg = 'contrail-vrouter-dkms'
                else:
                    vrouter_generic_pkg = sudo("apt-cache pkgnames contrail-vrouter-$(uname -r)")
                    contrail_vrouter_pkg = vrouter_generic_pkg or 'contrail-vrouter-dkms'

                dpdk = getattr(env, 'dpdk', None)
                if dpdk:
                    if env.host_string in dpdk:
                        contrail_vrouter_pkg = 'contrail-vrouter-dpdk-init'

                pkg = [contrail_vrouter_pkg, 'contrail-openstack-vrouter']

            if (manage_nova_compute == 'no' and ostype in ['centos', 'redhat']):
                pkg = ['contrail-vrouter-common',
                       'openstack-utils',
                       'contrail-nova-vif',
                      ]
            elif (manage_nova_compute== 'no' and ostype in ['ubuntu']):
                pkg = [contrail_vrouter_pkg,
                       'contrail-vrouter-common'
                      ]
            if getattr(testbed, 'haproxy', False):
                pkg.append('haproxy')
            if (ostype == 'ubuntu' and is_lbaas_enabled()):
                pkg.append('haproxy')
                pkg.append('iproute')

            if ostype == 'ubuntu':
                sudo('echo "manual" >> /etc/init/supervisor-vrouter.override')
                if get_hypervisor(host_string) == 'docker':
                    pkg.append('nova-docker')
                apt_install(pkg)
            else:
                yum_install(pkg)
            install_ceilometer_compute_node(host_string)

@task
@EXECUTE_TASK
@roles('all')
def create_install_repo():
    """Creates contrail install repo in all nodes."""
    execute("create_install_repo_node", env.host_string)

@task
@roles('build')
def create_install_repo_without_openstack():
    """Creates contrail install repo in all nodes excluding openstack node."""
    host_strings = copy.deepcopy(env.roledefs['all'])
    dummy = [host_strings.remove(openstack_node)
             for openstack_node in env.roledefs['openstack']]
    for host_string in host_strings:
        with settings(host_string=host_string):
            execute("create_install_repo_node", host_string)

@task
def create_install_repo_node(*args):
    """Creates contrail install repo in one or list of nodes. USAGE:fab create_install_repo_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            contrail_setup_pkg = sudo("ls /opt/contrail/contrail_install_repo/contrail-setup*")
            contrail_setup_pkgs = contrail_setup_pkg.split('\n')
            if (len(contrail_setup_pkgs) == 1 and
                get_release() in contrail_setup_pkgs[0] and
                get_build().split('~')[0] in contrail_setup_pkgs[0]):
                print "Contrail install repo created already in node: %s." % host_string
                continue
            sudo("sudo /opt/contrail/contrail_packages/setup.sh")

@task
def create_install_repo_dpdk_node(*args):
    """Creates contrail install dpdk repo in one or list of nodes.
    USAGE:fab create_install_repo_dpdk_node:user@1.1.1.1,user@2.2.2.2
    """
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            # Install/uprgade dpdk-depends-packages
            sudo("apt-get install dpdk-depends-packages")

            # Setup repo. Script handles automatically case when repo is
            # already in /etc/apt/sources.list
            sudo("/opt/contrail/contrail_packages_dpdk/setup.sh")

@task
@roles('compute')
def create_install_repo_dpdk():
    """Creates contrail install dpdk repo on compute nodes configured with
    DPDK mode.
    """
    dpdk = getattr(env, 'dpdk', None)
    if dpdk:
        if env.host_string in dpdk:
            create_install_repo_dpdk_node(env.host_string)

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
    elif os_type in ['centos', 'redhat', 'fedora']:
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
    elif os_type in ['centos', 'redhat', 'fedora']:
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
def install_contrail(reboot='True'):
    """Installs required contrail packages in all nodes as per the role definition.
    """
    execute('pre_check')
    execute(create_install_repo)
    execute(create_install_repo_dpdk)
    execute(install_database)
    execute('install_orchestrator')
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    execute(install_vrouter)
    execute(upgrade_pkgs)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name, reboot)
    execute('reboot_on_kernel_update', reboot)

@roles('build')
@task
def install_without_openstack(manage_nova_compute='yes', reboot='True'):
    """Installs required contrail packages in all nodes as per the role definition except the openstack.
       User has to install the openstack node with their custom openstack pakckages.
       If manage_nova_compute = no, User has to install nova-compute in the compute node.
    """
    execute(create_install_repo_without_openstack)
    execute(create_install_repo_dpdk)
    execute(install_database)
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    execute('install_vrouter', manage_nova_compute)
    execute(upgrade_pkgs_without_openstack)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name, reboot)
    execute('reboot_on_kernel_update', reboot)

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
    elif detect_ostype() in ['centos', 'fedora', 'redhat']:
        sudo('yum install -y xorg-x11-server-Xvfb')
        sudo('wget http://ftp.mozilla.org/pub/mozilla.org/firefox/releases/33.0/linux-x86_64/en-US/firefox-33.0.tar.bz2')
        sudo('tar -xjvf firefox-33.0.tar.bz2')
        sudo('sudo mv firefox /opt/firefox')
        sudo('sudo ln -sf /opt/firefox/firefox /usr/bin/firefox')
#end install_webui_packages

@task
def update_config_option(role, file_path, section, option, value, service):
    """Task to update config option of any section in a conf file
       USAGE:fab update_config_option:openstack,/etc/keystone/keystone.conf,token,expiration,86400,keystone
    """
    cmd1 = "openstack-config --set " + file_path + " " +  section + " " + option + " " + value
    cmd2= "service " + service + " restart"
    for host in env.roledefs[role]:
        with settings(host_string=host, password=get_env_passwords(host)):
            sudo(cmd1)
            sudo(cmd2)
# end update_config_option

import os
import re
import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.cluster import is_lbaas_enabled, get_orchestrator
from fabfile.utils.host import get_from_testbed_dict, get_openstack_internal_vip
from fabfile.tasks.helpers import reboot_node

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
                pkgname = local("rpm -qpi %s | grep Name: | cut -d':' -f2" % pkg, capture=True).strip()
            elif pkg.endswith('.deb'):
                pkgname = local("dpkg --info %s | grep Package: | cut -d':' -f2" % pkg, capture=True).strip()
            build = get_build(pkgname)
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


def upgrade_rpm(rpm):
    rpm_name = os.path.basename(rpm)
    temp_dir= tempfile.mkdtemp()
    run('mkdir -p %s' % temp_dir)
    put(rpm, '%s/%s' % (temp_dir, rpm_name))
    run("rpm --upgrade --force -v %s/%s" % (temp_dir, rpm_name))

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
                run(cmd)

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
            run(cmd + rpm)

def apt_install(debs):
    cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes --allow-unauthenticated install "
    if detect_ostype() in ['ubuntu']:
        for deb in debs:
            run(cmd + deb)

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
    if detect_ostype() in ['ubuntu', 'redhat']:
        print "[%s]: Installing interface rename package not required for Ubuntu/Redhat..Skipping it" %env.host_string
    else:
        execute("install_interface_name_node", env.host_string, reboot=reboot)

@task
def install_interface_name_node(*args, **kwargs):
    """Installs interface name package in one or list of nodes. USAGE:fab install_interface_name_node:user@1.1.1.1,user@2.2.2.2"""
    if len(kwargs) == 0:
        reboot = 'True'
    else:
        reboot = kwargs['reboot']
    for host_string in args:
        with settings(host_string=host_string):
            rpm = ['contrail-interface-name']
            yum_install(rpm)
            if reboot == 'True':
                execute(reboot_node, env.host_string)

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
                run('echo "manual" >> /etc/init/supervisor-database.override')
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
            pkg = ['ceilometer-agent-compute']
            act_os_type = detect_ostype()
            if act_os_type == 'ubuntu':
                apt_install(pkg)
            else:
                raise RuntimeError('Actual OS Type (%s) != Expected OS Type (%s)'
                                    'Aborting!' % (act_os_type, 'ubuntu'))

@task
@EXECUTE_TASK
@roles('openstack')
def install_ceilometer():
    """Installs ceilometer pkgs in all nodes defined in first node of openstack role."""
    if env.roledefs['openstack'] and env.host_string == env.roledefs['openstack'][0]:
        execute("install_ceilometer_node", env.host_string)

@task
def install_ceilometer_node(*args):
    """Installs openstack pkgs in one or list of nodes. USAGE:fab install_ceilometer_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg_havana = ['mongodb', 'ceilometer-api',
                'ceilometer-collector',
                'ceilometer-agent-central',
                'python-ceilometerclient']
            pkg_icehouse = ['mongodb', 'ceilometer-api',
                'ceilometer-collector',
        	'ceilometer-agent-central',
        	'ceilometer-agent-notification',
        	'ceilometer-alarm-evaluator',
        	'ceilometer-alarm-notifier',
        	'python-ceilometerclient']
            act_os_type = detect_ostype()
            if act_os_type == 'ubuntu':
                #if not is_package_installed('mongodb-server'):
                #    raise RuntimeError('install_ceilometer: mongodb-server is required to be installed for ceilometer')
                output = run("dpkg-query --show nova-api")
                if output.find('2013.2') != -1:
                    apt_install(pkg_havana)
                elif output.find('2014.1') != -1:
                    apt_install(pkg_icehouse)
                else:
                    print "install_ceilometer: openstack dist unknown.. assuming icehouse.."
                    apt_install(pkg_icehouse)
            else:
                raise RuntimeError('Actual OS Type (%s) != Expected OS Type (%s)'
                                    'Aborting!' % (act_os_type, 'ubuntu'))

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
                run('echo "manual" >> /etc/init/supervisor-config.override')
                run('echo "manual" >> /etc/init/neutron-server.override')
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
                run('echo "manual" >> /etc/init/supervisor-control.override')
                run('echo "manual" >> /etc/init/supervisor-dns.override')
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
                run('echo "manual" >> /etc/init/supervisor-analytics.override')
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
                run('echo "manual" >> /etc/init/supervisor-webui.override')
                apt_install(pkg)
            else:
                yum_install(pkg)


@task
@EXECUTE_TASK
@roles('compute')
def install_vrouter(manage_nova_compute='yes'):
    """Installs vrouter pkgs in all nodes defined in vrouter role."""
    if env.roledefs['compute']:
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
        ostype = detect_ostype()
        with  settings(host_string=host_string):
            pkg = ['contrail-openstack-vrouter']
            if (manage_nova_compute == 'no' and ostype in ['centos']):
                pkg = ['contrail-vrouter',
                       'abrt',
                       #'openstack-nova-compute',
                       'openstack-utils',
                       'python-thrift',
                       #'librabbitmq',
                       'contrail-nova-vif',
                       'contrail-setup',
                       'contrail-nodemgr',
                       'contrail-vrouter-init',
                      ]
            elif (manage_nova_compute== 'no' and ostype in ['ubuntu']):
                pkg = ['contrail-nodemgr',
                       'contrail-setup',
                       'contrail-vrouter-init',
                       #'nova-compute',
                       'python-iniparse',
                       #'python-novaclient',
                       'contrail-nova-vif',
                       #'librabbitmq0',
                       'linux-crashdump',
                       'contrail-vrouter'
                      ]
            if getattr(testbed, 'haproxy', False):
                pkg.append('haproxy')
            if (ostype == 'ubuntu' and is_lbaas_enabled()):
                pkg.append('haproxy')
                pkg.append('iproute')

            if ostype == 'ubuntu':
                run('echo "manual" >> /etc/init/supervisor-vrouter.override')
                apt_install(pkg)
            else:
                yum_install(pkg)

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
            contrail_setup_pkg = run("ls /opt/contrail/contrail_install_repo/contrail-setup*")
            contrail_setup_pkgs = contrail_setup_pkg.split('\n')
            if (len(contrail_setup_pkgs) == 1 and get_release() in contrail_setup_pkgs[0]):
                print "Contrail install repo created already in node: %s." % host_string
                continue
            run("sudo /opt/contrail/contrail_packages/setup.sh")

@roles('build')
@task
def install_orchestrator():
    if get_orchestrator() is 'openstack':
        execute(install_openstack)

@roles('build')
@task
def install_contrail(reboot='True'):
    """Installs required contrail packages in all nodes as per the role definition.
    """
    execute('pre_check')
    execute(create_install_repo)
    execute(install_database)
    execute('install_orchestrator')
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    execute(install_vrouter)
    execute(upgrade_pkgs)
    execute(update_keystone_log)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name, reboot)

@roles('build')
@task
def install_without_openstack(manage_nova_compute='yes'):
    """Installs required contrail packages in all nodes as per the role definition except the openstack.
       User has to install the openstack node with their custom openstack pakckages.
       If manage_nova_compute = no, User has to install nova-compute in the compute node.
    """
    execute(create_install_repo_without_openstack)
    execute(install_database)
    execute(install_cfgm)
    execute(install_control)
    execute(install_collector)
    execute(install_webui)
    execute('install_vrouter', manage_nova_compute)
    execute(upgrade_pkgs_without_openstack)
    if getattr(env, 'interface_rename', True):
        print "Installing interface Rename package and rebooting the system."
        execute(install_interface_name)

@roles('openstack')
@task
def update_keystone_log():
    """Temporary workaround to update keystone log"""
    #TODO This is a workaround. Need to be fixed as part of package install
    if detect_ostype() in ['ubuntu']:
        with  settings(warn_only=True):
            run("touch /var/log/keystone/keystone.log")
            run("sudo chown keystone /var/log/keystone/keystone.log")
            run("sudo chgrp keystone /var/log/keystone/keystone.log")


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
        run('cp ' + source_dir + '/contrail-test/scripts/ubuntu_repo/sources.list /etc/apt')
        run('sudo apt-get -y update')
        run('sudo apt-get install -y xvfb')
        if webui == 'firefox':
            run('sudo apt-get install -y firefox')
            run('sudo apt-get remove -y firefox')
            run('wget https://ftp.mozilla.org/pub/mozilla.org/firefox/releases/31.0/linux-x86_64/en-US/firefox-31.0.tar.bz2')
            run('tar -xjvf firefox-31.0.tar.bz2')
            run('sudo mv firefox /opt/firefox')
            run('sudo ln -sf /opt/firefox/firefox /usr/bin/firefox')
        elif webui == 'chrome':
            run('echo "deb http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee -a /etc/apt/sources.list')
            run('wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -')
            run('sudo apt-get -y update')
            run('sudo apt-get -y install unzip')
            run('wget -c http://chromedriver.storage.googleapis.com/2.10/chromedriver_linux64.zip')
            run('unzip chromedriver_linux64.zip')
            run('sudo cp ./chromedriver /usr/bin/')
            run('sudo chmod ugo+rx /usr/bin/chromedriver')
            run('sudo apt-get -y install libxpm4 libxrender1 libgtk2.0-0 libnss3 libgconf-2-4')
            run('sudo apt-get -y install google-chrome-stable')
    elif detect_ostype() in ['centos', 'fedora', 'redhat']:
        run('yum install -y xorg-x11-server-Xvfb')
        run('wget http://ftp.mozilla.org/pub/mozilla.org/firefox/releases/33.0/linux-x86_64/en-US/firefox-33.0.tar.bz2')
        run('tar -xjvf firefox-33.0.tar.bz2')
        run('sudo mv firefox /opt/firefox')
        run('sudo ln -sf /opt/firefox/firefox /usr/bin/firefox')
#end install_webui_packages 

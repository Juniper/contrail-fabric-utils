import os
import re
import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import get_openstack_internal_vip, get_from_testbed_dict

def get_pkg_list():
    dont_remove_list = [
                        'contrail-install-packages',
                        'contrail-fabric-utils',
                        'contrail-interface-name',
                        'glib2',
                        'glibc',
                        'glibc-common',
                        'libgcc',
                        'make',
                        'pkgconfig',
                        'python',
                        'python-libs',
                       ]
    output = run('yum list installed | grep @contrail_install_repo | cut -d" " -f1 | cut -d"." -f1')
    pkgs = output.split("\r\n")
    for pkg in dont_remove_list:
        try:
            pkgs.remove(pkg)
        except ValueError:
            pass
    return pkgs

@task
@EXECUTE_TASK
@roles('all')
def uninstall_rpm_all(rpm):
    """Uninstalls any rpm in all nodes."""
    execute('uninstall_pkg_node', rpm, env.host_string)

@task
@EXECUTE_TASK
@roles('all')
def uninstall_deb_all(deb):
    """Uninstalls any deb in all nodes."""
    execute('uninstall_pkg_node', deb, env.host_string)

@task
@EXECUTE_TASK
@roles('all')
def uninstall_pkg_all(pkg):
    """Uninstalls any rpm/deb package in all nodes."""
    execute('uninstall_pkg_node', pkg, env.host_string)

@task
@roles('build')
def uninstall_pkg_all_without_openstack(pkg):
    """Uninstalls any rpm/deb package in all nodes excluding openstack node."""
    host_strings = copy.deepcopy(env.roledefs['all'])
    dummy = [host_strings.remove(openstack_node)
             for openstack_node in env.roledefs['openstack']]
    execute('uninstall_pkg_node', pkg, *host_strings)

@task
def uninstall_pkg_node(pkg, *args):
    """Uninstalls any rpm/deb in one node."""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            build = get_build()
            if not build:
                print "Package %s already uninstalled in the node(%s)." % (pkg, host_string)
                continue
            if detect_ostype() == 'ubuntu':
                apt_uninstall([pkg])
            else:
                yum_uninstall([pkg])


def yum_uninstall(rpms):
    cmd = "rpm -e "
    if detect_ostype() in ['centos', 'fedora', 'redhat']:
        with settings(warn_only=True):
            run(cmd + ' '.join(rpms))

def apt_uninstall(debs):
    cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes autoremove --purge "
    if detect_ostype() in ['ubuntu']:
        with settings(warn_only=True):
            run(cmd + ' '.join(debs))

@task
@EXECUTE_TASK
@roles('all')
def cleanup_opt_contrail():
    run("sudo rm -rf /opt/contrail")

@task
@EXECUTE_TASK
@roles('compute')
def uninstall_interface_name():
    """Uninstalls interface name package in all nodes defined in compute role."""
    if not env.roledefs['compute']:
        return
    if detect_ostype() == 'ubuntu':
        print "[%s]: uninstalling interface rename package not required for Ubuntu..Skipping it" %env.host_string
    else:
        execute("uninstall_interface_name_node", env.host_string)

@task
def uninstall_interface_name_node(*args):
    """Uninstalls interface name package in one or list of nodes. USAGE:fab uninstall_interface_name_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            rpm = ['contrail-interface-name']
            yum_uninstall(rpm)
            run('rm -f /etc/sysconfig/network-scripts/ifcfg-p*p*p*')

@task
@EXECUTE_TASK
@roles('database')
def uninstall_database():
    """Uninstalls database pkgs in all nodes defined in database."""
    if env.roledefs['database']:
        execute("uninstall_database_node", env.host_string)

@task
def uninstall_database_node(*args):
    """Uninstalls database pkgs in one or list of nodes. USAGE:fab uninstall_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-database']
            if detect_ostype() == 'ubuntu':
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/etc/'):
                run('sudo rm -rf zookeeper')
            with cd('/var/lib/'):
                run('sudo rm -rf /usr/share/cassandra /var/cassandra_log /var/crashes /home/cassandra')
                run('sudo rm -rf /var/log/cassandra /var/log/zookeeper')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*')

@task
@EXECUTE_TASK
@roles('openstack')
def uninstall_openstack():
    """Uninstalls openstack pkgs in all nodes defined in openstack role."""
    if env.roledefs['openstack']:
        execute("uninstall_openstack_node", env.host_string)

@task
def uninstall_openstack_node(*args):
    """Uninstalls openstack pkgs in one or list of nodes. USAGE:fab uninstall_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack']
            if len(env.roledefs['openstack']) > 1 and get_openstack_internal_vip():
                pkg.append('contrail-openstack-ha')
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    run("umount /var/lib/glance/images")
                run("sed -i '/.*glance.*/d' /etc/fstab")
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/etc/'):
                run('sudo rm -rf glance/ cinder/ openstack_dashboard/ keystone/ quantum/ nova/ haproxy/ keepalived/')
            with cd('/var/lib/'):
                run('sudo rm -rf nova quantum glance quantum keystone mysql haproxy')
            with cd('/var/run'):
                run('sudo rm -rf cinder glance quantum nova keystone')
            with cd('/var/log'):
                run('sudo rm -rf contrail/* nova quantum glance cinder /root/keystone-signing /tmp/keystone-signing /tmp/keystone-signing-nova')

@task
@EXECUTE_TASK
@roles('cfgm')
def uninstall_cfgm():
    """Uninstalls config pkgs in all nodes defined in cfgm role."""
    if env.roledefs['cfgm']:
        execute("uninstall_cfgm_node", env.host_string)

@task
def uninstall_cfgm_node(*args):
    """Uninstalls config pkgs in one or list of nodes. USAGE:fab uninstall_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-config']
            if detect_ostype() == 'ubuntu':
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/etc/'):
                run('sudo rm -rf irond haproxy keepalived')
            with cd('/var/lib/'):
                run('sudo rm -rf haproxy')
                run('sudo rm -rf /var/crashes')
            with cd('/usr/share'):
                run('sudo rm -rf irond')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*') 


@task
@EXECUTE_TASK
@roles('control')
def uninstall_control():
    """Uninstalls control pkgs in all nodes defined in control role."""
    if env.roledefs['control']:
        execute("uninstall_control_node", env.host_string)

@task
def uninstall_control_node(*args):
    """Uninstalls control pkgs in one or list of nodes. USAGE:fab uninstall_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-control']
            if detect_ostype() == 'ubuntu':
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/var/'):
                run('sudo rm -rf crashes')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*')


@task
@EXECUTE_TASK
@roles('collector')
def uninstall_collector():
    """Uninstalls analytics pkgs in all nodes defined in collector role."""
    if env.roledefs['collector']:
        execute("uninstall_collector_node", env.host_string)

@task
def uninstall_collector_node(*args):
    """Uninstalls analytics pkgs in one or list of nodes. USAGE:fab uninstall_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            pkg = ['contrail-openstack-analytics']
            if detect_ostype() == 'ubuntu':
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/var/lib/'):
                run('sudo rm -rf redis')
                run('sudo rm -rf /var/crashes')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*')

@task
@EXECUTE_TASK
@roles('webui')
def uninstall_webui():
    """Uninstalls webui pkgs in all nodes defined in webui role."""
    if env.roledefs['webui']:
        execute("uninstall_webui_node", env.host_string)

@task
def uninstall_webui_node(*args):
    """Uninstalls webui pkgs in one or list of nodes. USAGE:fab uninstall_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            with settings(warn_only=True):
                run("stop_webui")
                run("kill -9  $(pidof redis-server)")
            pkg = ['contrail-openstack-webui']
            if detect_ostype() == 'ubuntu':
                apt_uninstall(pkg)
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/var/'):
                run('sudo rm -rf crashes')
            with cd('/opt/contrail'):
                run('sudo rm -rf nodejs*')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*')


@task
@EXECUTE_TASK
@roles('compute')
def uninstall_vrouter(manage_nova_compute='yes'):
    """Uninstalls vrouter pkgs in all nodes defined in vrouter role."""
    if env.roledefs['compute']:
        execute("uninstall_only_vrouter_node", manage_nova_compute, env.host_string)

@task
def uninstall_vrouter_node(*args):
    """Uninstalls nova compute and vrouter pkgs in one or list of nodes. USAGE:fab uninstall_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute('uninstall_only_vrouter_node', 'yes', *args)

@task
def uninstall_only_vrouter_node(manage_nova_compute='yes', *args):
    """Uninstalls only vrouter pkgs in one or list of nodes. USAGE:fab uninstall_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no, User has to uninstall nova-compute in the compute node.
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
            if ostype == 'ubuntu':
                apt_uninstall(pkg)
                run("sed -i  's/inet manual/inet dhcp/g' /etc/network/interfaces")
            else:
                pkgs = get_pkg_list()
                yum_uninstall(pkgs)
            with cd('/etc/'):
                run('sudo rm -rf libvirt')
                with settings(warn_only=True):
                    run('find ./contrail/* ! -iname \'contrail_ifrename.sh\' -delete')
            with cd('/var/'):
                run('sudo rm -rf crashes')
                run('sudo rm -rf tmp')
            with cd('/var/log'):
                run('sudo rm -rf contrail/*')


@roles('build')
@task
def uninstall_contrail(full='no'):
    """Uninstalls required contrail packages in all nodes as per the role definition.
    
    Note that contrail-install-packages package is still 
    retained so that a new uninstall/setup can be run using : 
        fab install_contrail
        fab setup_all
    
    To force a full cleanup, set full=True as argument. 
    This will remove contrail-install-packages as well
    """
    execute(uninstall_database)
    execute(uninstall_openstack)
    execute(uninstall_cfgm)
    execute(uninstall_control)
    execute(uninstall_collector)
    execute(uninstall_webui)
    execute(uninstall_vrouter)
    if getattr(env, 'interface_rename', True):
        execute(uninstall_interface_name)
    if full == 'yes':
        pkgs = ['contrail-install-packages', 'contrail-fabric-utils', 'contrail-setup']
        for pkg in pkgs:
            execute('uninstall_pkg_all', pkg)
        execute('cleanup_opt_contrail')
    execute('reboot_all_build_atlast')


@roles('build')
@task
def uninstall_without_openstack(manage_nova_compute='yes', full='no'):
    """Uninstalls required contrail packages in all nodes as per the role definition except the openstack.
       User has to uninstall the openstack node with their custom openstack pakckages.
       If subset of contrail-openstack-vrouter package is installed, pass manage_nova_compute = no

    Note that contrail-install-packages package is still 
    retained so that a new uninstall/setup can be run using : 
        fab install_contrail
        fab setup_all
    
    To force a full cleanup, set full=True as argument. 
    This will remove contrail-install-packages as well
    """
    execute(uninstall_database)
    execute(uninstall_cfgm)
    execute(uninstall_control)
    execute(uninstall_collector)
    execute(uninstall_webui)
    execute('uninstall_vrouter', manage_nova_compute)
    if getattr(env, 'interface_rename', True):
        execute(uninstall_interface_name)
    if full == 'yes':
        pkgs = ['contrail-install-packages', 'contrail-fabric-utils', 'contrail-setup']
        for pkg in pkgs:
            execute('uninstall_pkg_all', pkg)
        execute('cleanup_opt_contrail')
    execute('reboot_all_build_atlast')


@task
@roles('build')
def reboot_all_build_atlast():
    """Reboot all nodes, will reboot the node from where fab command is trrigered at last"""
    if env.host_string in env.roledefs['all']:
        #Trrigered from one of the node in cluster
        node_list_except_build = copy.deepcopy(env.roledefs['all'])
        node_list_except_build.remove(env.host_string)
        execute("reboot_nodes_atlast", *node_list_except_build)
        execute("reboot_nodes_atlast", env.host_string)
    else:
        #Trrigered from external machine
        nodes = copy.deepcopy(env.roledefs['all'])
        execute("reboot_nodes_atlast", *nodes)


@task
def reboot_nodes_atlast(*args):
    """reboots the given nodes"""
    for host_string in args:
        with settings(host_string=host_string):
            print "Rebooting (%s)..." % host_string
            try:
                sudo('reboot --force', timeout=3)
            except CommandTimeout:
                pass

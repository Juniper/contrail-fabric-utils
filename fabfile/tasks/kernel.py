from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro
from fabfile.utils.cluster import get_nodes_to_upgrade_pkg, reboot_nodes, get_package_installed_info
from fabfile.tasks.install import apt_install, pkg_install


@task
@roles('build')
def upgrade_kernel_all(*tgzs, **kwargs):
    """creates repo and upgrades kernel in Ubuntu"""
    reboot = kwargs.get('reboot', 'yes')
    execute('create_installer_repo')
    execute('create_install_repo', *tgzs)
    nodes = []
    with settings(host_string=env.roledefs['all'][0], warn_only=True):
        dist, version, extra = get_linux_distro()
        if version == '12.04':
            (package, os_type) = ('linux-image-3.13.0-34-generic', 'ubuntu')
        elif version == '14.04':
            (package, os_type) = ('linux-image-3.13.0-40-generic', 'ubuntu')
        else:
            raise RuntimeError("Unsupported platfrom (%s, %s, %s) for"
                               " kernel upgrade." % (dist, version, extra))
    nodes = get_nodes_to_upgrade_pkg(package, os_type, *env.roledefs['all'])
    if not nodes:
        print "kernel is already of expected version"
        return
    execute(upgrade_kernel_node, *nodes)
    if reboot == 'yes':
        node_list_except_build = list(nodes)
        if env.host_string in nodes:
            node_list_except_build.remove(env.host_string)
            reboot_nodes(*node_list_except_build)
            reboot_nodes(env.host_string)
        else:
            reboot_nodes(*nodes)

@task
@roles('build')
def upgrade_kernel_without_openstack(*tgzs, **kwargs):
    """creates repo and upgrades kernel"""
    reboot = kwargs.get('reboot', 'yes')
    non_openstack_nodes = [node for node in env.roledefs['all'] if node not in env.roledefs['openstack']]
    execute('create_installer_repo')
    execute('create_install_repo_without_openstack', *tgzs)
    nodes = []
    with settings(host_string=env.roledefs['cfgm'][0], warn_only=True):
        dist, version, extra = get_linux_distro()

    if 'red hat' in dist.lower() and version == '7.0':
        (package, os_type) = ('kernel-3.10.0-229.el7.x86_64', 'redhat')
    else:
        raise RuntimeError("Unsupported platfrom (%s, %s, %s) for"
                           " kernel upgrade." % (dist, version, extra))
    nodes = get_package_installed_info(package, os_type, *non_openstack_nodes)
    if not nodes['not_installed']:
        print "Nodes are already booted with expected version"
        return
    if nodes['installed']:
        print "Nodes (%s) are already booted in expected "\
              "kernel version" % ", ".join(nodes['installed'])

    execute(upgrade_kernel_node, *nodes['not_installed'])
    if reboot == 'yes':
        if env.host_string in nodes:
            nodes.remove(env.host_string).append(env.host_string)
        reboot_nodes(*nodes['not_installed'])
    else:
        print "WARNING: Reboot Skipped as reboot=False; "\
              "Reboot manually to avoid misconfiguration"

@task
@EXECUTE_TASK
@roles('all')
def upgrade_kernel():
    """upgrades the kernel image in all nodes."""
    execute("upgrade_kernel_node", env.host_string)

@task
def upgrade_kernel_node(*args):
    """upgrades the kernel image in given nodes."""
    for host_string in args:
        with settings(host_string=host_string):
            dist, version, extra = get_linux_distro()
            if version == '12.04':
                print "upgrading apparmor before upgrading kernel"
                apt_install(["apparmor"])
                print "Installing 3.13.0-34 kernel headers"
                apt_install(["linux-headers-3.13.0-34"])
                apt_install(["linux-headers-3.13.0-34-generic"])
                print "Upgrading the kernel to 3.13.0-34"
                apt_install(["linux-image-3.13.0-34-generic"])
            elif version == '14.04':
                print "Installing 3.13.0-40 kernel headers"
                apt_install(["linux-headers-3.13.0-40",
                             "linux-headers-3.13.0-40-generic"])
                print "Upgrading the kernel to 3.13.0-40"
                apt_install(["linux-image-3.13.0-40-generic",
                             "linux-image-extra-3.13.0-40-generic"])
            elif 'red hat' in dist.lower() and version == '7.0':
                print "Upgrading kernel to version 3.10.0-229"
                pkg_install(["kernel-3.10.0-229.el7.x86_64",
                             "kernel-tools-3.10.0-229.el7.x86_64",
                             "kernel-tools-libs-3.10.0-229.el7.x86_64",
                             "kernel-headers-3.10.0-229.el7.x86_64"], disablerepo=False)

@task
@EXECUTE_TASK
@roles('compute')
def migrate_compute_kernel():
    execute('create_install_repo_node', env.host_string)
    execute('migrate_compute_kernel_node', env.host_string)

@task
def migrate_compute_kernel_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo('service supervisor-vrouter stop')
            sudo('apt-get -o Dpkg::Options::="--force-overwrite" -y install contrail-vrouter-3.13.0-40-generic')

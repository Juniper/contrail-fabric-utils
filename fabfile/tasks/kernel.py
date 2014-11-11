from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro
from fabfile.tasks.install import apt_install

@task
@roles('build')
def upgrade_kernel_all():
    """creates repo and upgrades kernel in Ubuntu"""
    execute('pre_check')
    execute('create_install_repo')
    dist, version, extra = get_linux_distro()
    nodes = []
    if version is '12.04':
        nodes = get_nodes_to_upgrade('linux-image-3.13.0-34-generic', 'ubuntu', *env.roledefs['all'])
    elif version is '14.04':
        nodes = get_nodes_to_upgrade('linux-image-3.13.0-35-generic', 'ubuntu', *env.roledefs['all'])
    if not nodes:
        print "kernel is already of expected version"
    execute(upgrade_kernel_node, *nodes)
    node_list_except_build = list(nodes)
    if env.host_string in nodes:
        node_list_except_build.remove(env.host_string)
        execute("reboot_nodes", *node_list_except_build)
        execute("reboot_nodes", env.host_string)
    else:
        execute("reboot_nodes", *nodes)

@task
def get_nodes_to_upgrade(package, os_type, *args):
    """get the list of nodes in which kernel needs to be upgraded"""
    nodes = []
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            act_os_type = detect_ostype()
            if act_os_type == os_type:
                version = run("dpkg -l | grep %s" % package)
                if not version:
                    nodes.append(host_string)
                else:
                    print 'Has required Kernel. Skipping!'
            else:
                raise RuntimeError('Actual OS Type (%s) != Expected OS Type (%s)'
                                    'Aborting!' % (act_os_type, os_type))
    return nodes

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
            print "upgrading apparmor before upgrading kernel"
            if version is '12.04':
                apt_install(["apparmor"])
                print "Installing 3.13.0-34 kernel headers"
                apt_install(["linux-headers-3.13.0-34"])
                apt_install(["linux-headers-3.13.0-34-generic"])
                print "Upgrading the kernel to 3.13.0-34"
                apt_install(["linux-image-3.13.0-34-generic"])
            elif version is '14.04':
                print "Upgrading the kernel to 3.13.0-35"
                apt_install(["linux-image-3.13.0-35-generic",
                             "linux-image-extra-3.13.0-35-generic"])

@task
def reboot_nodes(*args):
    """reboots the given nodes"""
    for host_string in args:
        with settings(host_string=host_string):
            print "Rebooting (%s) to boot with new kernel version" % host_string
            try:
                sudo('reboot --force', timeout=3)
            except CommandTimeout:
                pass

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro
from fabfile.utils.cluster import get_nodes_to_upgrade_pkg, reboot_nodes
from fabfile.tasks.install import apt_install


@task
@roles('build')
def upgrade_kernel_all(reboot='yes'):
    """creates repo and upgrades kernel in Ubuntu"""
    execute('pre_check')
    execute('create_install_repo')
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
            if version == '12.04':
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

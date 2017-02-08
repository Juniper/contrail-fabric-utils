from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro
from fabfile.utils.cluster import get_nodes_to_upgrade_pkg, reboot_nodes, get_package_installed_info
from fabfile.tasks.install import apt_install, pkg_install


@task
def set_grub_default_node(*args, **kwargs):
    '''Set default kernel version to bootup for given list of nodes'''
    value = kwargs.get('value')
    for host_string in args:
        with settings(host_string=host_string):
            dist, version, extra = get_linux_distro()
            if 'ubuntu' in dist.lower():
                sudo("sed -i \'s/^GRUB_DEFAULT=.*/GRUB_DEFAULT=\"%s\"/g\' /etc/default/grub" % value)
                sudo('update-grub')
                sudo("grep '^GRUB_DEFAULT=\"%s\"' /etc/default/grub" % value)
            elif 'red hat' in dist.lower() or 'centos linux' in dist.lower():
                sudo("grub2-set-default \'%s\'" % value)
                sudo('grub2-mkconfig -o /boot/grub2/grub.cfg')
                sudo("grub2-editenv list | grep \'%s\'" % value)
            print '[%s]: Updated Default Grub to (%s)' % (host_string, value)

@task
@roles('all')
def set_grub_default(value='Advanced options for Ubuntu>Ubuntu, with Linux 3.13.0-106-generic'):
    '''Set default kernel version to bootup for all nodes'''
    execute('set_grub_default_node', env.host_string, value=value)

@task
@roles('build')
def upgrade_kernel_all(*tgzs, **kwargs):
    """creates repo and upgrades kernel in Ubuntu"""
    reboot = kwargs.get('reboot', 'yes')
    execute('create_installer_repo')
    execute('create_install_repo', *tgzs)
    nodes = []
    kernel_ver = kwargs.get('version')
    with settings(host_string=env.roledefs['all'][0], warn_only=True):
        dist, version, extra = get_linux_distro()
        if version == '12.04':
            (package, os_type) = ('linux-image-3.13.0-34-generic', 'ubuntu')
            default_grub='Advanced options for Ubuntu>Ubuntu, with Linux 3.13.0-34-generic'
        elif version == '14.04':
            if kernel_ver is None:
                kernel_ver='3.13.0-106'
            (package, os_type) = ('linux-image-'+kernel_ver+'-generic', 'ubuntu')
            default_grub='Advanced options for Ubuntu>Ubuntu, with Linux '+kernel_ver+'-generic'
        elif 'centos linux' in dist.lower() and version.startswith('7'):
            (package, os_type) = ('kernel-3.10.0-327.10.1.el7.x86_64', 'centoslinux')
        elif 'red hat' in dist.lower() and version.startswith('7'):
            (package, os_type) = ('kernel-3.10.0-327.10.1.el7.x86_64', 'redhat')
        else:
            raise RuntimeError("Unsupported platfrom (%s, %s, %s) for"
                               " kernel upgrade." % (dist, version, extra))
    nodes = get_nodes_to_upgrade_pkg(package, os_type, *env.roledefs['all'])
    if not nodes:
        print "kernel is already of expected version"
        return
    execute(upgrade_kernel_node, *nodes, **kwargs)
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

    if ('red hat' in dist.lower() or 'centos linux' in dist.lower()) and version.startswith('7'):
        (package, os_type) = ('kernel-3.10.0-327.10.1.el7.x86_64', 'redhat')
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

    execute(upgrade_kernel_node, *nodes['not_installed'], **kwargs)
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
def upgrade_kernel(**kwargs):
    """upgrades the kernel image in all nodes."""
    execute("upgrade_kernel_node", env.host_string, **kwargs)

@task
def upgrade_kernel_node(*args, **kwargs):
    """upgrades the kernel image in given nodes."""
    for host_string in args:
        with settings(host_string=host_string):
            execute('create_install_repo_node', host_string)
            dist, version, extra = get_linux_distro()
            if version == '12.04':
                print "upgrading apparmor before upgrading kernel"
                apt_install(["apparmor"])
                print "Installing 3.13.0-34 kernel headers"
                apt_install(["linux-headers-3.13.0-34"])
                apt_install(["linux-headers-3.13.0-34-generic"])
                print "Upgrading the kernel to 3.13.0-34"
                apt_install(["linux-image-3.13.0-34-generic"])
                default_grub='Advanced options for Ubuntu>Ubuntu, with Linux 3.13.0-34-generic'
                execute('set_grub_default_node', host_string, value=default_grub)
            elif version == '14.04':
                if 'version' in kwargs:
                    kernel_ver = kwargs.get('version')
                else:
                    kernel_ver = "3.13.0-106"
                print "Installing "+kernel_ver+" kernel headers"
                apt_install(["linux-headers-"+kernel_ver,
                             "linux-headers-"+kernel_ver+"-generic"])
                print "Upgrading the kernel to "+kernel_ver
                apt_install(["linux-image-"+kernel_ver+"-generic",
                             "linux-image-extra-"+kernel_ver+"-generic"])
                default_grub='Advanced options for Ubuntu>Ubuntu, with Linux '+kernel_ver+'-generic'
                execute('set_grub_default_node', host_string, value=default_grub)
            elif 'red hat' in dist.lower() and version.startswith('7'):
                print "Upgrading RHEL kernel to version 3.10.0-327.10.1"
                pkg_install(["kernel-3.10.0-327.10.1.el7.x86_64",
                             "kernel-tools-3.10.0-327.10.1.el7.x86_64",
                             "kernel-tools-libs-3.10.0-327.10.1.el7.x86_64",
                             "kernel-headers-3.10.0-327.10.1.el7.x86_64"], disablerepo=False)
                default_grub='Red Hat Enterprise Linux Server (3.10.0-327.10.1.el7.x86_64) 7.2 (Maipo)'
                execute('set_grub_default_node', host_string, value=default_grub)
            elif 'centos linux' in dist.lower() and version.startswith('7'):
                print "Upgrading Centos kernel to version 3.10.0-327.10.1"
                pkg_install(["kernel-3.10.0-327.10.1.el7.x86_64",
                             "kernel-tools-3.10.0-327.10.1.el7.x86_64",
                             "kernel-tools-libs-3.10.0-327.10.1.el7.x86_64",
                             "kernel-headers-3.10.0-327.10.1.el7.x86_64"], disablerepo=False)
                default_grub='CentOS Linux (3.10.0-327.10.1.el7.x86_64) 7 (Core)'
                execute('set_grub_default_node', host_string, value=default_grub)

@task
@EXECUTE_TASK
@roles('compute')
def migrate_compute_kernel(**kwargs):
    execute('create_install_repo_node', env.host_string)
    execute('migrate_compute_kernel_node', env.host_string, **kwargs)

@task
def migrate_compute_kernel_node(*args, **kwargs):
    for host_string in args:
        with settings(host_string=host_string):
            out = sudo('service supervisor-vrouter status')
            if 'stop' not in out:
                sudo('service supervisor-vrouter stop')
            if 'version' in kwargs:
                kernel_ver = kwargs.get('version')
            else:
                kernel_ver = "3.13.0-106"
            sudo('apt-get -o Dpkg::Options::="--force-overwrite" -y install contrail-vrouter-'+kernel_ver+'-generic')
            upgrade_kernel_node(host_string, **kwargs)

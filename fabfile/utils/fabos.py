import os
import ast
import tempfile

from fabfile.config import *

def copy_pkg(tgt_host, pkg_file):
    with settings(host_string = tgt_host):
        put(pkg_file, use_sudo=True)
#end _copy_pkg

def install_pkg(tgt_host, pkg_file):
    with settings(host_string = tgt_host):
        sudo("rpm -iv --force %s" %(pkg_file.split('/')[-1]))
#end _install_pkg

def get_linux_distro():
    linux_distro = "python -c 'from platform import linux_distribution; print linux_distribution()'"
    (dist, version, extra) = ast.literal_eval(sudo(linux_distro))
    return (dist, version, extra)

def detect_ostype():
    (dist, version, extra) = get_linux_distro()
    if extra is not None and 'xen' in extra:
        dist = 'xen'
    elif 'red hat' in dist.lower():
        dist = 'redhat'
    elif 'centos linux' in dist.lower():
        dist = 'centoslinux'

    return dist.lower()
#end detect_ostype

def get_openstack_sku(use_install_repo=False):
    dist = detect_ostype()
    if dist in ['ubuntu']:
        pkg = 'nova-common'
    elif dist in ['centos', 'fedora', 'redhat', 'centoslinux']:
        pkg = 'openstack-nova-common'
    else:
        print "Unsupported OS type"
        return None
    pkg_ver = get_release(pkg=pkg, use_install_repo=use_install_repo)
    if pkg_ver is None:
        return None
    if pkg_ver.find('2013.2') != -1:
        openstack_sku = 'havana'
    elif pkg_ver.find('2014.1') != -1:
        openstack_sku = 'icehouse'
    elif pkg_ver.find('2014.2') != -1:
        openstack_sku = 'juno'
    else:
        print "OpenStack distribution unknown.. assuming icehouse.."
        openstack_sku = 'icehouse'
    return openstack_sku
#end get_openstack_sku

def get_release(pkg='contrail-install-packages', use_install_repo=False):
    pkg_ver = None
    dist = detect_ostype() 
    print "Dist is %s" % dist
    if dist in ['centos', 'fedora', 'redhat', 'centoslinux']:
        if use_install_repo:
            cmd = "rpm -qp --queryformat '%%{VERSION}' /opt/contrail/contrail_install_repo/%s*.rpm 2> /dev/null" %pkg
        else:
            cmd = "rpm -q --queryformat '%%{VERSION}' %s" %pkg
    elif dist in ['ubuntu']:
        if use_install_repo:
            cmd = "dpkg --info /opt/contrail/contrail_install_repo/%s*.deb | grep Version: | cut -d' ' -f3 | cut -d'-' -f1" %pkg
        else:
            cmd = "dpkg -s %s | grep Version: | cut -d' ' -f2 | cut -d'-' -f1" %pkg
    pkg_ver = sudo(cmd)
    if 'is not installed' in pkg_ver or 'is not available' in pkg_ver or 'No such file or directory' in pkg_ver:
        print "Package %s not installed." % pkg
        return None
    return pkg_ver

def get_build(pkg='contrail-install-packages'):
    pkg_rel = None
    dist = detect_ostype()
    if dist in ['centos', 'fedora', 'redhat', 'centoslinux']:
        cmd = "rpm -q --queryformat '%%{RELEASE}' %s" %pkg
    elif dist in ['ubuntu']:
        cmd = "dpkg -s %s | grep Version: | cut -d' ' -f2 | cut -d'-' -f2" %pkg
    pkg_rel = sudo(cmd)
    if 'is not installed' in pkg_rel or 'is not available' in pkg_rel:
        print "Package %s not installed." % pkg
        return None
    return pkg_rel

def get_pkg_version_release(pkg='contrail-install-packages'):
    pkg_rel = None
    dist = detect_ostype()
    if dist in ['centos', 'fedora', 'redhat', 'centoslinux']:
        cmd = "rpm -q --queryformat '%%{VERSION}-%%{RELEASE}\\n' %s" % pkg
    elif dist in ['ubuntu']:
        cmd = "dpkg-query -W -f='${VERSION}\\n' %s" % pkg
    else:
        raise Exception("ERROR: Unknown dist (%s)" % dist)
    pkg_rel = sudo(cmd)
    if pkg_rel.failed or 'is not installed' in pkg_rel or 'is not available' in pkg_rel:
        print "Package %s not installed." % pkg
        return None
    return pkg_rel.split('\r\n') if pkg_rel else pkg_rel

def is_package_installed(pkg_name):
    ostype = detect_ostype()
    if ostype in ['ubuntu']:
        cmd = 'dpkg-query -l "%s" | grep -q ^.i'
    elif ostype in ['centos','fedora', 'centoslinux', 'redhat']:
        cmd = 'rpm -qi %s '
    cmd = cmd % (pkg_name)
    with settings(warn_only=True):
        result = sudo(cmd)
    return result.succeeded 
#end is_package_installed

def get_as_sudo(src_file, dst_file):
    basename = os.path.basename(src_file.rstrip('/'))
    if not basename or basename in ['*']:
        raise Exception('%s is not a valid path'%src_file)
    tempdir = run('(tempdir=$(mktemp -d); echo $tempdir)')
    tmp_file = '%s/tmp%s' % (tempdir, basename)
    sudo('cp -rf %s %s'%(src_file, tmp_file))
    sudo('chmod -R 777 %s'%tmp_file)
    try:
        status = get(tmp_file, dst_file)
        if os.path.isdir(dst_file):
            local('mv %s/tmp%s %s/%s' %(dst_file, basename, dst_file, basename))
    except:
        sudo('rm -rf %s' % tempdir)
        raise
    sudo('rm -rf %s' % tempdir)
#end get_as_sudo

def verify_command_succeeded(cmd, expected_output, error_str, max_count,
                             sleep_interval, warn_only):
    count = 1
    cmd_str = cmd
    if warn_only:
        with settings(warn_only=True):
            output = sudo(cmd)
    else:
        output = sudo(cmd)
    while not output.succeeded or output != expected_output:
        count += 1
        if count > max_count:
            raise RuntimeError("%s: %s %s" % (error_str, output.succeeded,\
                 output))
        sleep(sleep_interval)
        if warn_only:
            with settings(warn_only=True):
                output = sudo(cmd)
        else:
            output = sudo(cmd)
#end verify_command_succeeded

# Delete file
def remove_file(file_name):
    cmd = 'rm -f ' + file_name
    sudo(cmd)
#end remove_file

def get_available_packages(os_type, *packages):
    '''Retrieve packages version available in the node'''

    os_type = detect_ostype()
    pkg_dict = {}

    for package in packages:
        pkg_dict[package] = None
        versions = None
        with setting(warn_only=True):
            if os_type in ['centos', 'redhat', 'centoslinux', 'fedora']:
                versions = sudo("yum list %s | grep %s | awk -F ' ' '{print $2}'" %(package, package))
            elif os_type in ['ubuntu']:
                versions = sudo('apt-cache show %s | grep Version: | grep -Po "Version: \K.*"' % package)
            else:
                raise RuntimeError('UnSupported OS Type (%s)' % os_type)
        if versions:
            if versions.succeeded:
                pkg_dict[package] = versions.split('\r\n')
    return pkg_dict

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
    if 'red hat' in dist.lower():
        dist = 'redhat'
    return dist.lower()
#end detect_ostype

def get_release(pkg='contrail-install-packages'):
    pkg_ver = None
    dist = detect_ostype() 
    if dist in ['centos', 'fedora', 'redhat']:
        cmd = "rpm -q --queryformat '%%{VERSION}' %s" %pkg
    elif dist in ['ubuntu']:
        cmd = "dpkg -s %s | grep Version: | cut -d' ' -f2 | cut -d'-' -f1" %pkg
    pkg_ver = sudo(cmd)
    if 'is not installed' in pkg_ver or 'is not available' in pkg_ver:
        print "Package %s not installed." % pkg
        return None
    return pkg_ver

def get_build(pkg='contrail-install-packages'):
    pkg_rel = None
    dist = detect_ostype()
    if dist in ['centos', 'fedora', 'redhat']:
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
    if dist in ['centos', 'fedora', 'redhat']:
        cmd = "rpm -q --queryformat '%%{VERSION}-%%{RELEASE}\\n' %s" % pkg
    elif dist in ['ubuntu']:
        cmd = "dpkg-query -W -f='${VERSION}\\n' %s" % pkg
    else:
        raise Exception("ERROR: Unknown dist (%s)" % dist)
    pkg_rel = sudo(cmd) or None
    if pkg_rel.failed or 'is not installed' in pkg_rel or 'is not available' in pkg_rel:
        print "Package %s not installed." % pkg
        return None
    return pkg_rel.split('\r\n') if pkg_rel else pkg_rel

def is_package_installed(pkg_name):
    ostype = detect_ostype()
    if ostype in ['ubuntu']:
        cmd = 'dpkg-query -l "%s" | grep -q ^.i'
    elif ostype in ['centos','fedora']:
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

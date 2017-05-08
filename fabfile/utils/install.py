import os
import copy
import glob

from fabric.api import env, settings, sudo
from fabric.contrib.files import exists

from fabos import detect_ostype, get_release, get_build, get_openstack_sku
from fabfile.utils.host import (get_hypervisor, get_openstack_internal_vip,
        manage_config_db)
from fabfile.utils.cluster import is_lbaas_enabled, get_orchestrator
from fabfile.config import *
from fabfile.utils.fabos import is_xenial_or_above


def get_openstack_pkgs():
    pkgs = ['contrail-openstack']
    if len(env.roledefs['openstack']) > 1 and get_openstack_internal_vip():
        pkgs.append('contrail-openstack-ha')

    return pkgs

def get_vrouter_kmod_pkg():
    """Return the contrail-vrouter-dkms | contrail-vrouter-generic
       package to be installed in compute node depending on the kernel
       version.
    """
    ostype = detect_ostype()
    if ostype in ['ubuntu']:
        dkms_status = get_build('contrail-vrouter-dkms')
        if dkms_status is not None:
            contrail_vrouter_pkg = 'contrail-vrouter-dkms'
        else:
            # Search for matching contrail-vrouter pkg for kernel version in cache.
            vrouter_generic_pkg = sudo("apt-cache pkgnames contrail-vrouter-$(uname -r)")
            contrail_vrouter_pkg = vrouter_generic_pkg or 'contrail-vrouter-dkms'
    else:
        contrail_vrouter_pkg = None

    return contrail_vrouter_pkg

def get_compute_pkgs(manage_nova_compute='yes'):
    """Returns a list of packages to be installed in the
       compute node.
    """
    ostype = detect_ostype()

    if get_orchestrator() is 'vcenter':
        pkgs = ['contrail-vmware-vrouter']
    else:
        pkgs = ['contrail-openstack-vrouter']

    if ostype in ['ubuntu']:
        # For Ubuntu, Install contrail-vrouter-generic package if one available for
        # node's kernel version or install contrail-vrouter-dkms
        # If dkms is already installed, continue to upgrade contrail-vrouter-dkms
        contrail_vrouter_pkg = get_vrouter_kmod_pkg()

        if env.host_string in getattr(env, 'dpdk', []):
            contrail_vrouter_pkg = 'contrail-vrouter-dpdk-init'
        # This order of installation matters, because in a node with
        # non recommended kernel installed, contrail-vrouter-dkms pkg
        # needs to get installed first before contrail-openstack-vrouter.
        if get_orchestrator() is 'vcenter':
            pkgs = [contrail_vrouter_pkg, 'contrail-vmware-vrouter']
        else:
            pkgs = [contrail_vrouter_pkg, 'contrail-openstack-vrouter']

    # Append only vrouter and contrail vrouter dependent packages
    # no need to append the contrail-openstack-vrouter, which when
    # installed will bring in nova-compute and its dependents.
    if (manage_nova_compute == 'no' and ostype in ['centos', 'redhat', 'fedora', 'centoslinux']):
        pkgs = ['contrail-vrouter-common',
               'openstack-utils',
              ]
        if get_openstack_sku() in ['juno']:
            pkgs.append('contrail-nova-vif')
    elif (manage_nova_compute== 'no' and ostype in ['ubuntu']):
        pkgs = [contrail_vrouter_pkg,
               'contrail-vrouter-common']
	if get_orchestrator() is 'openstack':
            pkgs.append('contrail-nova-vif')
        else:
            pkgs.append('contrail-vmware-vrouter')
    # Append lbaas dependent packages if haproxy is enabled..
    if getattr(testbed, 'haproxy', False):
        pkgs.append('haproxy')

    # Append lbaas dependent packages if Lbaas is enabled..
    if is_lbaas_enabled():
        pkgs.append('haproxy')
        pkgs.append('iproute')

    if ostype == 'ubuntu':
        # Append nova-docker if hypervisor for this compute host is docker.
        if get_hypervisor(env.host_string) == 'docker':
            pkgs.append('nova-docker')

    return pkgs

def get_config_pkgs():
     if get_orchestrator() is 'vcenter':
         pkgs = ['contrail-vmware-config']
     else:
         pkgs = ['contrail-openstack-config']
     if manage_config_db:
         pkgs.append('contrail-database-common')

     return pkgs

def get_setup_vcenter_pkg():
     pkgs = ['python-pyvmomi']
 
     return pkgs

def get_vcenter_plugin_pkg():
    pkg = ['contrail-install-vcenter-plugin']

    return pkg

def get_vcenter_compute_pkgs():
    pkgs = ['nova-compute', 'nova-compute-kvm',
            'python-novaclient', 'python-bitstring',
            'contrail-utils']
    if is_xenial_or_above():
        pkgs += ['openjdk-8-jre-headless'] 
    else:
        pkgs += ['openjdk-7-jre-headless']

    return pkgs

def get_vcenter_plugin_depend_pkgs():
    pkgs = ['libxml-commons-external-java',
            'libxml-commons-resolver1.1-java',
            'libxerces2-java', 'libslf4j-java',
            'libnetty-java', 'libjline-java',
            'libzookeeper-java']

    return pkgs

def get_openstack_ceilometer_pkgs():
    """ Returns the list of ceilometer packages used in a
        openstack node.
    """
    pkg_ubuntu = ['ceilometer-api',
        'ceilometer-collector',
        'ceilometer-agent-central',
        'ceilometer-agent-notification',
        'ceilometer-plugin-contrail',
        'mongodb-clients',
        'python-pymongo']
    if get_openstack_sku() in ['juno', 'kilo', 'liberty']:
        pkg_ubuntu += [ 'ceilometer-alarm-evaluator',
                        'ceilometer-alarm-notifier']

    pkg_redhat = ['ceilometer-plugin-contrail']

    ceilometer_pkgs = {
        'ubuntu' : pkg_ubuntu,
        'redhat' : pkg_redhat,
    }

    act_os_type = detect_ostype()
    return ceilometer_pkgs.get(act_os_type, [])

def get_ceilometer_plugin_pkgs():
    """ Returns the list of ceilometer plugin packages used in a
        openstack node.
    """
    pkg_contrail_ceilometer = ['ceilometer-plugin-contrail']
    ceilometer_plugin_pkgs = {
        'ubuntu' : pkg_contrail_ceilometer,
        'redhat' : pkg_contrail_ceilometer,
    }
        
    act_os_type = detect_ostype()
    return ceilometer_plugin_pkgs.get(act_os_type, [])

def get_compute_ceilometer_pkgs():
    """ Returns the list of ceilometer packages used in a
        compute node.
    """
    pkgs = []
    ostype = detect_ostype()
    if ostype == 'ubuntu':
        pkgs = ['ceilometer-agent-compute']
    elif ostype == 'redhat':
        pkgs = ['openstack-ceilometer-compute']

    return pkgs

def get_net_driver_pkgs():
    """ Returns the list of network driver packages used in
        all the nodes
    """
    pkgs = []
    ostype = detect_ostype()
    if ostype == 'ubuntu':
        pkgs = ['i40e-dkms', 'bnxt-en-dkms']

    return pkgs

@task
def create_yum_repo_from_tgz_node(tgz, *args, **kwargs):
    '''Untar given tgz file and create a local yum repo'''

    extra_repo = kwargs.get('extra_repo', 'auto_check')
    tgz_in_target = kwargs.get('tgz_in_target', 'no')

    for host_string in args:
        with settings(host_string=host_string):
            tempdir = ''
            tgz_file_name = os.path.basename(tgz)
            tgz_name = os.path.splitext(tgz_file_name)
            repo_dir_name = os.path.join(os.path.sep, 'opt', 'contrail', tgz_name[0])
            sudo('mkdir -p %s' % repo_dir_name)

            # Check if tgz is available locally. no need to copy the tgz
            is_remote = None
            if tgz_in_target == 'yes':
                with settings(warn_only=True):
                    is_remote = sudo('ls %s' % tgz)
                    is_remote = is_remote.succeeded

            if not is_remote and host_string not in env.roledefs['build']:
                tempdir = sudo('mktemp -d')
                remote_path = os.path.join(tempdir, tgz_file_name)
                put(tgz, tempdir, use_sudo=True)
            else:
                remote_path = tgz

            # Untar the given tgz file and create repo
            sudo('tar xfz %s -C %s' % (remote_path, repo_dir_name))
            with cd(repo_dir_name):
                sudo('createrepo .')

            # remove temp dir if created
            if tempdir:
                sudo('rm -rf %s' % tempdir)

            repo_def = "[%s]\n" \
                       "name=%s\n" \
                       "baseurl=file://%s/\n" \
                       "enabled=1\n" \
                       "priority=1\n" \
                       "gpgcheck=0" % (tgz_name[0], tgz_name[0], repo_dir_name)

            # Add the repo entry
            if not exists('/etc/yum.repos.d/%s.repo' % tgz_name[0], use_sudo=True):
                sudo('echo \"%s\" > /etc/yum.repos.d/%s.repo' % (repo_def, tgz_name[0]))
            else:
                print 'WARNING: A repo entry (/etc/yum.repos.d/%s.repo) already exists' % tgz_name[0]
                print 'WARNING: Backup and recreate new one'
                node_date = sudo("date +%Y_%m_%d__%H_%M_%S")
                sudo('cp /etc/yum.repos.d/%s.repo /etc/yum.repos.d/%s.repo.%s.contrailbackup' % (
                     tgz_name[0], tgz_name[0], node_date))
                sudo('echo \"%s\" > /etc/yum.repos.d/%s.repo' % (repo_def, tgz_name[0]))

            # Update all repos
            with settings(warn_only=True):
                sudo('yum clean all')

            # recursively extract repo by default, if user has not overriden
            # extra_repo argument and if tgz contains no rpm packages
            # assuming cloud/networking tgz would not contain
            # rpm packages as such but tgz of debs
            with settings(warn_only=True):
                rpms_present = sudo('ls %s/*.rpm > /dev/null' % repo_dir_name)
                if rpms_present.failed and extra_repo == 'auto_check':
                    print 'Setting extra_repo = \'yes\''
                    extra_repo = 'yes'

            if extra_repo == 'yes':
                with settings(warn_only=True):
                    extra_tgzs = sudo('ls %s/*.tgz' % repo_dir_name)
                    if extra_tgzs.succeeded:
                        for tgzfile in extra_tgzs.split('\r\n'):
                            kwargs.update([('tgz_in_target', 'yes')])
                            # Recrucively extract the tgzs present in given tgz
                            create_yum_repo_from_tgz_node(tgzfile, host_string, **kwargs)


@task
def create_apt_repo_from_tgz_node(tgz, *args, **kwargs):
    '''Untar given tgz file and create a local apt repo'''

    extra_repo = kwargs.get('extra_repo', 'auto_check')
    tgz_in_target = kwargs.get('tgz_in_target', 'no')

    for host_string in args:
        with settings(host_string=host_string):
            tempdir = ''
            tgz_file_name = os.path.basename(tgz)
            tgz_name = os.path.splitext(tgz_file_name)
            repo_dir_name = os.path.join(os.path.sep, 'opt', 'contrail', tgz_name[0])
            sudo('mkdir -p %s' % repo_dir_name)

            # Check if tgz is available locally. no need to copy the tgz
            is_remote = None
            if tgz_in_target == 'yes':
                with settings(warn_only=True):
                    is_remote = sudo('ls %s' % tgz)
                    is_remote = is_remote.succeeded

            if not is_remote and host_string not in env.roledefs['build']:
                tempdir = sudo('mktemp -d')
                remote_path = os.path.join(tempdir, tgz_file_name)
                put(tgz, tempdir, use_sudo=True)
            else:
                remote_path = tgz

            # Untar the given tgz file and create repo
            sudo('tar xfz %s -C %s' % (remote_path, repo_dir_name))

            with cd(repo_dir_name):
                sudo('dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz')

            if tempdir:
                sudo('rm -rf %s' % tempdir)

            # Add the repo entry
            with settings(warn_only=True):
                is_repo_entry_exists = sudo('grep "^deb file:%s ./" /etc/apt/sources.list' % repo_dir_name)
            if is_repo_entry_exists.failed:
                node_date = sudo("date +%Y_%m_%d__%H_%M_%S")
                sudo('cp /etc/apt/sources.list /etc/apt/sources.list.%s.contrailbackup' % node_date)
                sudo('echo >> /etc/apt/sources.list')
                sudo("sed -i '1 i\deb file:%s ./' /etc/apt/sources.list" % repo_dir_name)
            else:
                print "Warning: A repo entry to (%s) already exists in /etc/apt/sources.list"

            # Update all repos
            with settings(warn_only=True):
                sudo("apt-get update")

            # recursively extract repo by default, if user has not overriden
            # extra_repo argument and if tgz contains no debian packages
            # assuming cloud/networking tgz would not contain
            # debian packages as such but tgz of debs
            with settings(warn_only=True):
                debs_present = sudo('ls %s/*.deb > /dev/null' % repo_dir_name)
                if debs_present.failed and extra_repo == 'auto_check':
                    print 'Setting extra_repo = \'yes\''
                    extra_repo = 'yes'

            if extra_repo == 'yes':
                with settings(warn_only=True):
                    extra_tgzs = sudo('ls %s/*.tgz' % repo_dir_name)
                    if extra_tgzs.succeeded:
                        for tgzfile in extra_tgzs.split('\r\n'):
                            kwargs.update([('tgz_in_target', 'yes')])
                            # Recrucively extract the tgzs present in given tgz
                            create_apt_repo_from_tgz_node(tgzfile, host_string, **kwargs)

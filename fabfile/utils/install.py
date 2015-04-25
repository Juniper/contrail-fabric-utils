from fabric.api import env, settings, sudo

from fabos import detect_ostype, get_release, get_build, get_openstack_sku
from fabfile.utils.host import get_hypervisor
from fabfile.utils.cluster import is_lbaas_enabled
from fabfile.config import *


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
        pkgs = [contrail_vrouter_pkg, 'contrail-openstack-vrouter']

    # Append only vrouter and contrail vrouter dependent packages
    # no need to append the contrail-openstack-vrouter, which when
    # installed will bring in nova-compute and its dependents.
    if (manage_nova_compute == 'no' and ostype in ['centos', 'redhat']):
        pkgs = ['contrail-vrouter-common',
               'openstack-utils',
               'contrail-nova-vif',
              ]
    elif (manage_nova_compute== 'no' and ostype in ['ubuntu']):
        pkgs = [contrail_vrouter_pkg,
               'contrail-vrouter-common'
              ]
    # Append lbaas dependent packages if haproxy is enabled..
    if getattr(testbed, 'haproxy', False):
        pkgs.append('haproxy')

    # Append lbaas dependent packages if Lbaas is enabled..
    if (ostype == 'ubuntu' and is_lbaas_enabled()):
        pkgs.append('haproxy')
        pkgs.append('iproute')

    if ostype == 'ubuntu':
        # Append nova-docker if hypervisor for this compute host is docker.
        if get_hypervisor(env.host_string) == 'docker':
            pkgs.append('nova-docker')

    return pkgs

def get_openstack_ceilometer_pkgs():
    """ Returns the list of ceilometer packages used in a
        openstack node.
    """
    pkg_havana_ubuntu = ['mongodb', 'ceilometer-api',
        'ceilometer-collector',
        'ceilometer-agent-central',
        'python-ceilometerclient']
    pkg_icehouse_ubuntu = pkg_havana_ubuntu + [
        'ceilometer-agent-notification',
        'ceilometer-alarm-evaluator',
        'ceilometer-alarm-notifier',
        'ceilometer-plugin-contrail']
    pkg_juno_ubuntu = pkg_icehouse_ubuntu + [
        'mongodb-server',
        'mongodb-clients',
        'python-pymongo']
    pkg_juno_ubuntu.remove('mongodb')
    pkg_icehouse_redhat = ['ceilometer-plugin-contrail']

    ceilometer_pkgs = {
        'ubuntu' : {'havana' : pkg_havana_ubuntu,
                    'icehouse' : pkg_icehouse_ubuntu,
                    'juno' : pkg_juno_ubuntu
                   },
        'redhat' : {'icehouse' : pkg_icehouse_redhat},
    }

    act_os_type = detect_ostype()
    openstack_sku = get_openstack_sku()
    return ceilometer_pkgs.get(act_os_type, {}).get(openstack_sku, [])

def get_ceilometer_plugin_pkgs():
    """ Returns the list of ceilometer plugin packages used in a
        openstack node.
    """
    pkg_contrail_ceilometer = ['ceilometer-plugin-contrail']
    ceilometer_plugin_pkgs = {
        'ubuntu' : {'icehouse' : pkg_contrail_ceilometer,
                    'juno' : pkg_contrail_ceilometer
                   },
        'redhat' : {'icehouse' : pkg_contrail_ceilometer},
    }
        
    act_os_type = detect_ostype()
    openstack_sku = get_openstack_sku()
    return ceilometer_plugin_pkgs.get(act_os_type, {}).get(openstack_sku, [])

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

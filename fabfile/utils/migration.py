import os
from fabric.api import *
from fabfile.config import testbed
from fabfile.utils.host import *
from fabfile.utils.cluster import get_all_hostnames

# reads and returns nova live-migration config from testbed.py
def get_live_migration_enable():
    return getattr(testbed, 'live_migration', False)
#end get_live_migration_enable

# reads and returns nfs live-migration config from testbed.py
def get_ceph_nfs_migration_enable():
    return getattr(testbed, 'ceph_nfs_livem', False)
#end get_ceph_nfs_migration_enable

# reads and returns external nfs live-migration config from testbed.py
def get_ext_nfs_migration_enable():
    return getattr(testbed, 'ext_nfs_livem', False)
#end get_ext_nfs_migration_enable

# reads and returns Ceph vm nfs server subnet from testbed.py
def get_ceph_nfs_migration_subnet():
    return getattr(testbed, 'ceph_nfs_livem_subnet', None)
#end get_ceph_nfs_migration_subnet

# reads and returns Ceph vm nfs server qcow2 image from testbed.py
def get_ceph_nfs_migration_image():
    return getattr(testbed, 'ceph_nfs_livem_image', None)
#end get_ceph_nfs_migration_image

# reads and returns Ceph vm nfs server host from testbed.py
# The host should be part of the compute nodes
def get_ceph_nfs_migration_host():
    entry = getattr(testbed, 'ceph_nfs_livem_host', None)
    for sthostname, sthostentry in zip(get_all_hostnames(), env.roledefs['all']):
        if entry == sthostentry:
            return sthostname
#end get_ceph_nfs_migration_host

# reads and returns external nfs mount point from testbed.py
def get_ext_nfs_migration_mount():
    return getattr(testbed, 'ext_nfs_livem_mount', None)
#end get_ext_nfs_migration_mount

# reads and returns nova uid fix config from testbed.py
def get_nova_uid_fix_enabled():
    return getattr(testbed, 'nova_uid_fix', None)
#end get_nova_uid_fix_enabled

# Returns all the nfs live-migration related configuration
# for provisioning.
def get_nfs_live_migration_opts(no_nfs):
    nfs_live_migration_opts = "disabled"
    # if no_nfs is set, then ignore all
    # Ceph_nfs live-migration configuration and
    # external nfs live-migration configuration
    if no_nfs == 1:
        return nfs_live_migration_opts
    if get_ext_nfs_migration_enable():
        nfs_live_migration_opts = "enabled --nfs-livem-mount %s" %(get_ext_nfs_migration_mount())
    elif get_ceph_nfs_migration_enable():
        nfs_live_migration_opts = "enabled --nfs-livem-subnet %s --nfs-livem-image %s --nfs-livem-host %s" %(get_ceph_nfs_migration_subnet(), get_ceph_nfs_migration_image(), get_ceph_nfs_migration_host())
    return nfs_live_migration_opts
#end get_nfs_live_migration_opts

# Returns nova live-migration configuration for
# provisioning
def get_live_migration_opts():
    live_migration_opts = "disabled"
    if get_live_migration_enable():
        live_migration_opts = "enabled"
    return live_migration_opts
#end get_live_migration_opts

# Returns whether nova uid fix is required or not
def get_nova_uid_fix_opt():
    nova_uid_fix_opt = "disabled"
    if get_nova_uid_fix_enabled():
        nova_uid_fix_opt = "enabled"
    return nova_uid_fix_opt
#end get_nova_uid_fix_opt

def get_live_migration_scope():
    return getattr(testbed, 'live_migration_scope', 'disabled')

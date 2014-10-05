import os
from fabric.api import *
from fabfile.config import testbed
from fabfile.utils.host import *

def get_live_migration_enable():
    return getattr(testbed, 'live_migration', False)

def get_ceph_nfs_migration_enable():
    return getattr(testbed, 'ceph_nfs_livem', False)

def get_ext_nfs_migration_enable():
    return getattr(testbed, 'ext_nfs_livem', False)

def get_ceph_nfs_migration_subnet():
    return getattr(testbed, 'ceph_nfs_livem_subnet', None)

def get_ceph_nfs_migration_image():
    return getattr(testbed, 'ceph_nfs_livem_image', None)

def get_ceph_nfs_migration_host():
    entry = getattr(testbed, 'ceph_nfs_livem_host', None)
    for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
        if entry == sthostentry:
            return sthostname

def get_ext_nfs_migration_mount():
    return getattr(testbed, 'ext_nfs_livem_mount', None)

def get_nfs_live_migration_opts():
    nfs_live_migration_opts = "disabled"
    if get_ext_nfs_migration_enable():
        nfs_live_migration_opts = "enabled --nfs-livem-mount %s" %(get_ext_nfs_migration_mount())
    elif get_ceph_nfs_migration_enable():
        nfs_live_migration_opts = "enabled --nfs-livem-subnet %s --nfs-livem-image %s --nfs-livem-host %s" %(get_ceph_nfs_migration_subnet(), get_ceph_nfs_migration_image(), get_ceph_nfs_migration_host())
    return nfs_live_migration_opts

def get_live_migration_opts():
    live_migration_opts = "disabled"
    if get_live_migration_enable():
        live_migration_opts = "enabled"
    return live_migration_opts

from fabfile.config import testbed

def get_live_migration_enable():
    return getattr(testbed, 'live_migration', False)

def get_ceph_nfs_migration_enable():
    return getattr(testbed, 'ceph_nfs_livem', False)

def get_ceph_nfs_migration_subnet():
    return getattr(testbed, 'ceph_nfs_livem_subnet', None)

def get_ceph_nfs_migration_image():
    return getattr(testbed, 'ceph_nfs_livem_image', None)

def get_nfs_live_migration_opts():
    nfs_live_migration_opts = "disabled"
    if get_ceph_nfs_migration_enable():
        nfs_live_migration_opts = "enabled --nfs-livem-subnet %s --nfs-livem-image %s" %(get_ceph_nfs_migration_subnet(), get_ceph_nfs_migration_image())
    return nfs_live_migration_opts

def get_live_migration_opts():
    live_migration_opts = "disabled"
    if get_live_migration_enable():
        live_migration_opts = "enabled"
    return live_migration_opts

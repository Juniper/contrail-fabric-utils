from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.utils.migration import *
from fabfile.utils.storage import *
from fabfile.utils.analytics import *

@task
@EXECUTE_TASK
@roles('webui')
def setup_webui_storage(mode):
    """Provisions storage webui services."""

    #Get the webui host
    host_string = env.host_string

    #Get webui ip based on host
    storage_webui_ip = hstr_to_ip(host_string)

    #get webui host password
    storage_webui_host_password = env.passwords[host_string]

    cinder_vip = get_cinder_ha_vip()
    if cinder_vip != 'none':
        #if HA setup get the cinder vip address
        storage_rest_ip = cinder_vip
    else:
        #Get the storage master host
        storage_master = env.roledefs['storage-master'][0]
        #Get the storage master ip address (assuming ceph-rest-api server running)
        storage_rest_ip = hstr_to_ip(storage_master)

    with  settings(host_string = storage_webui_ip, password = storage_webui_host_password):
        with cd(INSTALLER_DIR):
             # Argument details
             # storage-setup-mode - setup/unconfigure/reconfigure
             # storage-webui-ip - Storage WebUI IP
             # storage-master-ip - storage master node where ceph-rest-api server is running
             cmd= "PASSWORD=%s setup-vnc-storage-webui --storage-setup-mode %s --storage-webui-ip %s  --storage-rest-ip %s --storage-disk-config %s --storage-ssd-disk-config %s"\
                     %(storage_webui_host_password, mode, storage_webui_ip, storage_rest_ip, ' '.join(get_storage_disk_config()), ' '.join(get_storage_ssd_disk_config()), )
             print cmd
             sudo(cmd)
#end setup_webui_storage

global storage_master
global storage_master_password

def create_storage_setup_cmd(mode):
    global storage_master
    global storage_master_password
    storage_host_entries=[]
    storage_pass_list=[]
    storage_host_list=[]
    storage_hostnames=[]
    collector_pass_list=[]
    collector_host_list=[]
    cfg_host_list=[]
    storage_os_pass_list=[]
    storage_os_host_list=[]
    storage_compute_hostnames=[]
    index = 0
    for entry in env.roledefs['storage-master']:
        for sthostname, sthostentry in zip(env.hostnames['all'],
                                                env.roledefs['all']):
            if entry == sthostentry:
                storage_hostnames.append(sthostname)
                storage_host_password=env.passwords[entry]
                storage_pass_list.append(storage_host_password)
                storage_host = get_control_host_string(entry)
                storage_data_ip=get_data_ip(storage_host)[0]
                storage_host_list.append(storage_data_ip)
                if index != 0:
                    storage_os_pass_list.append(storage_host_password)
                    storage_os_host_list.append(storage_data_ip)
                index = index + 1
    for entry in env.roledefs['storage-compute']:
        for sthostname, sthostentry in zip(env.hostnames['all'],
                                                env.roledefs['all']):
            if entry == sthostentry:
                storage_compute_hostnames.append(sthostname)

            if entry == sthostentry and \
                            entry != env.roledefs['storage-master'][0]:
                storage_hostnames.append(sthostname)
                storage_host_password=env.passwords[entry]
                storage_pass_list.append(storage_host_password)
                storage_host = get_control_host_string(entry)
                storage_data_ip=get_data_ip(storage_host)[0]
                storage_host_list.append(storage_data_ip)
    for entry in env.roledefs['collector']:
        for sthostname, sthostentry in zip(env.hostnames['all'],
                                                env.roledefs['all']):
            if entry == sthostentry:
                collector_pass_list.append(env.passwords[entry])
                collector_host = get_control_host_string(entry)
                collector_data_ip=get_data_ip(collector_host)[0]
                collector_host_list.append(collector_data_ip)
    index = 0
    for entry in env.roledefs['cfgm']:
        for sthostname, sthostentry in zip(env.hostnames['all'],
                                                env.roledefs['all']):
            if entry == sthostentry:
                if index != 0:
                    cfg_host = get_control_host_string(entry)
                    cfg_data_ip=get_data_ip(cfg_host)[0]
                    cfg_host_list.append(cfg_data_ip)
                index = index + 1

    if cfg_host_list == []:
        cfg_host_list.append('none')

    if storage_os_host_list == []:
        storage_os_host_list.append('none')

    if storage_os_pass_list == []:
        storage_os_pass_list.append('none')

    storage_master=env.roledefs['storage-master'][0]
    storage_master_ip=get_data_ip(storage_master)[0]
    cfm = env.roledefs['cfgm'][0]
    cfm_ip = get_data_ip(cfm)[0]
    storage_master_password=env.passwords[env.roledefs['storage-master'][0]]
    # Argument details
    # storage-setup-mode - setup/unconfigure/reconfigure - First time 
    #                      setup/Remove all configuration/Do a reconfigure
    # storage-master - Storage master IP
    # storage-hostnames - hostnames of all the nodes (storage master +
    #                     storage compute)
    # storage-host-tokens - password for all the nodes (storage master +
    #                       storage compute)
    # storage-disk-config - Disk list for Ceph combined pool or HDD pool
    # storage-chassis-config - Chassis information list in the form
    #                          of 'host1:id0 host2:id0 host3:id1'
    # storage-ssd-disk-config - Disk list for Ceph SSD pool
    # storage-journal-config - OSD journal disk list
    # storage-local-disk-config - Disk list for local LVM pool
    # storage-local-ssd-disk-config - Disk list for local LVM SSD pool
    # storage-local-nfs-disk-config - NFS storage list
    # storage-directory-config - Directory list for Ceph
    # live-migration - Enable/Disable live migration
    # collector-hosts - hosts of all collector nodes
    # collector-host-tokens - password for all collector nodes
    # cfg-host - first config node address (similar to storage-master)
    # cinder-vip - cinder internal vip address
    # config-hosts - config node address list (except cfg-host)
    # storage-os-hosts - storage openstack hosts (except storage-master)
    # storage-os-host-tokens - storage openstack hosts passwd list
    # storage-mon-hosts - storage hosts with monitors
    # cfg-vip -- cfg internal vip address
    # storage-compute-hostnames - hostnames of all storage compute nodes
    # WARNING: If anything is added in the arguments, make sure it
    # doesn't break add_storage_node task.
    cmd = "PASSWORD=%s setup-vnc-storage --storage-setup-mode %s --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-ssd-disk-config %s --storage-journal-config %s --storage-local-disk-config %s --storage-local-ssd-disk-config %s --storage-nfs-disk-config %s --storage-directory-config %s --storage-chassis-config %s --live-migration %s --collector-hosts %s --collector-host-tokens %s --cfg-host %s --cinder-vip %s --config-hosts %s --storage-os-hosts %s --storage-os-host-tokens %s --storage-mon-hosts %s --cfg-vip %s --storage-compute-hostnames %s" \
            %(storage_master_password, mode, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_ssd_disk_config()), ' '.join(get_storage_journal_config()), ' '.join(get_storage_local_disk_config()), ' '.join(get_storage_local_ssd_disk_config()), ' '.join(get_storage_nfs_disk_config()), ' '.join(get_storage_directory_config()), ' '.join(get_storage_chassis_config()), get_live_migration_opts(), ' '.join(collector_host_list), ' '.join(collector_pass_list), cfm_ip, get_cinder_ha_vip(), ' '.join(cfg_host_list), ' '.join(storage_os_host_list), ' '.join(storage_os_pass_list), ' '.join(get_storage_mon_hosts()), get_cfg_ha_vip(), ' '.join(storage_compute_hostnames))
    return cmd


@task
@EXECUTE_TASK
@roles('storage-master')
def setup_master_storage(mode):
    """Provisions storage master services."""
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        cmd = create_storage_setup_cmd(mode)
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                print cmd
                sudo(cmd)
#end setup_storage_master


@task
@EXECUTE_TASK
@roles('storage-master')
def setup_nfs_live_migration(mode):
    """Provisions nfs vm for live migration and live migration related configuration."""
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        storage_host_entries=[]
        storage_pass_list=[]
        storage_host_list=[]
        storage_hostnames=[]
        # One storage master is enough to configure nfs live-migration
        entry = env.roledefs['storage-master'][0]
        for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
            if entry == sthostentry:
                storage_hostnames.append(sthostname)
                storage_host_password=env.passwords[entry]
                storage_pass_list.append(storage_host_password)
                storage_host = get_control_host_string(entry)
                storage_data_ip=get_data_ip(storage_host)[0]
                storage_host_list.append(storage_data_ip)
        for entry in env.roledefs['storage-compute']:
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry and entry != env.roledefs['storage-master'][0]:
                    storage_hostnames.append(sthostname)
                    storage_host_password=env.passwords[entry]
                    storage_pass_list.append(storage_host_password)
                    storage_host = get_control_host_string(entry)
                    storage_data_ip=get_data_ip(storage_host)[0]
                    storage_host_list.append(storage_data_ip)
        storage_master=env.roledefs['storage-master'][0]
        storage_master_ip=get_data_ip(storage_master)[0]
        storage_master_password=env.passwords[env.roledefs['storage-master'][0]]
        cfm = env.roledefs['cfgm'][0]
        cfm_ip = get_data_ip(cfm)[0]

        if storage_master_ip != cfm_ip:
            with  settings(host_string = storage_master, password = storage_master_password):
                sudo('mkdir -p %s' %(os.path.dirname(get_ceph_nfs_migration_image())))
                put(get_ceph_nfs_migration_image(), os.path.dirname(get_ceph_nfs_migration_image()), use_sudo=True)

        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                # Argument details
                # storage-setup-mode - setup/unconfigure/reconfigure - First time nfs livemigration configurations/Unconfigure/Reconfigure
                # storage-master - Storage master IP
                # storage-hostnames - hostnames of all the nodes (storage master + storage compute)
                # storage-host-tokens - password for all the nodes (storage master + storage compute)
                # live-migration - Enable/Disable live migration
                # nfs-live-migration - NFS Livemigration configuration (Image path, subnet, host)
                cmd= "PASSWORD=%s setup-vnc-livemigration --storage-setup-mode %s --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-directory-config %s --live-migration %s --nfs-live-migration %s" \
                    %(storage_master_password, mode, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts(), get_nfs_live_migration_opts())
                print cmd
                sudo(cmd)
#end setup_nfs_live_migration_services

@task
@EXECUTE_TASK
@roles('storage-compute')
def setup_compute_storage():
    """Provisions storage compute services."""
    execute("setup_storage_compute_node", env.host_string)

@task
def setup_storage_compute_node(*args):
	"""Provisions storage compute services in one or list of nodes"""
	#dummy for now
	return

@task
@roles('build')
def unconfigure_storage():
    """UnProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "unconfigure")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "unconfigure")
#end unconfigure_storage

@task
@roles('build')
def storage_chassis_configure():
    """ReProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "chassis_configure")
    execute(setup_compute_storage)
#end storage_chassis_configure

@task
@roles('build')
def reconfigure_storage():
    """ReProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "reconfigure")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "reconfigure")
#end reconfigure_storage

@task
@roles('build')
def setup_storage():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "setup")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "setup")
#end setup_storage


@task
@roles('build')
def setup_upgrade_storage():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "upgrade")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "upgrade")
#end setup_storage


@task
@roles('build')
def setup_nfs_livem():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "setup")
#end setup_nfs_livem

@task
@roles('build')
def setup_nfs_livem_global():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "setup_global")
#end setup_nfs_livem_global

# Function to remove node/nodes from existing cluster
# The syntax is fab remove_storage_node cmbu-ceph-3,cmbu-ceph-2
@task
@roles('storage-master')
def remove_storage_node(*args):
    """Removes an OSD from existing Ceph cluster"""
    print args
    delete_host_list = []
    for entries in args:
        delete_host_list.append(entries)
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        cmd = create_storage_setup_cmd('remove_host')
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                cmd += ' --hosts-to-remove %s' %(' '.join(delete_host_list))
                print cmd
                sudo(cmd)

# Function to remove osd/osds from existing cluster
# The syntax is fab remove_disk cmbu-ceph-3:/dev/sdd,cmbu-ceph-2:/dev/sde
@task
@roles('storage-master')
def remove_disk(*args):
    """Removes an Disk from existing Storage configuration"""
    print args
    delete_osd_list = []
    for entries in args:
        delete_osd_list.append(entries)
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        cmd = create_storage_setup_cmd('remove_disk')
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                cmd += ' --disks-to-remove %s' %(' '.join(delete_osd_list))
                print cmd
                sudo(cmd)

@task
@roles('build')
def unconfigure_nfs_livem():
    """UnProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "unconfigure")
#end unconfigure_nfs_livem

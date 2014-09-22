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
    for entry in env.roledefs['webui']:
        #Get the webui host
        webui_host = entry
        #Get webui ip based on host
        storage_webui_ip= hstr_to_ip(webui_host)
        #get webui host password
        storage_webui_host_password=env.passwords[entry]
        #Get the storage master host
        storage_master=env.roledefs['storage-master'][0]
        #Get the storage master ip address (assuming ceph-rest-api server running)
        storage_master_ip=hstr_to_ip(storage_master)

        with  settings(host_string = storage_webui_ip, password = storage_webui_host_password):
            with cd(INSTALLER_DIR):
                 # Argument details
                 # storage-setup-mode - setup/unconfigure/reconfigure
                 # storage-webui-ip - Storage WebUI IP
                 # storage-master-ip - storage master node where ceph-rest-api server is running

                 cmd= "PASSWORD=%s python setup-vnc-storage-webui.py --storage-setup-mode %s --storage-webui-ip %s  --storage-master-ip %s --storage-disk-config %s --storage-ssd-disk-config %s"\
                         %(storage_webui_host_password, mode, storage_webui_ip, storage_master_ip, ' '.join(get_storage_disk_config()), ' '.join(get_storage_ssd_disk_config()), )
                 print cmd
                 run(cmd)
#end setup_webui_storage


@task
@EXECUTE_TASK
@roles('storage-master')
@task
def setup_master_storage(mode):
    """Provisions storage master services."""
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        storage_host_entries=[]
        storage_pass_list=[]
        storage_host_list=[]
        storage_hostnames=[]
        for entry in env.roledefs['storage-master']:
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
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                # Argument details
                # storage-setup-mode - setup/unconfigure/reconfigure - First time setup/Remove all configuration/Do a reconfigure
                # storage-master - Storage master IP
                # storage-hostnames - hostnames of all the nodes (storage master + storage compute)
                # storage-host-tokens - password for all the nodes (storage master + storage compute)
                # storage-disk-config - Disk list for Ceph combined pool or HDD pool
                # storage-ssd-disk-config - Disk list for Ceph SSD pool
                # storage-journal-config - OSD journal disk list
                # storage-local-disk-config - Disk list for local LVM pool
                # storage-local-ssd-disk-config - Disk list for local LVM SSD pool
                # storage-local-nfs-disk-config - NFS storage list
                # storage-directory-config - Directory list for Ceph
                # live-migration - Enable/Disable live migration
                cmd= "PASSWORD=%s python setup-vnc-storage.py --storage-setup-mode %s --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-ssd-disk-config %s --storage-journal-config %s --storage-local-disk-config %s --storage-local-ssd-disk-config %s --storage-nfs-disk-config %s --storage-directory-config %s --live-migration %s" \
                        %(storage_master_password, mode, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_ssd_disk_config()), ' '.join(get_storage_journal_config()), ' '.join(get_storage_local_disk_config()), ' '.join(get_storage_local_ssd_disk_config()), ' '.join(get_storage_nfs_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts())
                print cmd
                run(cmd)
#end setup_storage_master


@task
@EXECUTE_TASK
@roles('storage-master')
@task
def setup_nfs_live_migration(mode):
    """Provisions nfs vm for live migration and live migration related configuration."""
    host_string = env.host_string
    if host_string == env.roledefs['storage-master'][0]:
        storage_host_entries=[]
        storage_pass_list=[]
        storage_host_list=[]
        storage_hostnames=[]
        for entry in env.roledefs['storage-master']:
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
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                # Argument details
                # storage-setup-mode - setup/unconfigure/reconfigure - First time nfs livemigration configurations/Unconfigure/Reconfigure
                # storage-master - Storage master IP
                # storage-hostnames - hostnames of all the nodes (storage master + storage compute)
                # storage-host-tokens - password for all the nodes (storage master + storage compute)
                # live-migration - Enable/Disable live migration
                # nfs-live-migration - NFS Livemigration configuration (Image path, subnet, host)
                cmd= "PASSWORD=%s python setup-vnc-livemigration.py --storage-setup-mode %s --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-directory-config %s --live-migration %s --nfs-live-migration %s" \
                    %(storage_master_password, mode, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts(), get_nfs_live_migration_opts())
                print cmd
                run(cmd)
#end setup_nfs_live_migration_services

@task
def setup_add_storage_compute_node(*args):
	"""Add a storage compute services in one or list of nodes"""
        host_string = env.roledefs['storage-master'][0]
        storage_host_entries=[]
        storage_pass_list=[]
        storage_host_list=[]
        storage_hostnames=[]
        for entry in env.roledefs['storage-master']:
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    storage_hostnames.append(sthostname)
                    storage_host_password=env.passwords[entry]
                    storage_pass_list.append(storage_host_password)
                    storage_host = get_control_host_string(entry)
                    storage_data_ip=get_data_ip(storage_host)[0]
                    storage_host_list.append(storage_data_ip)
        new_host_entry = args[0]
        for entry in env.roledefs['storage-compute']:
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry and entry != env.roledefs['storage-master'][0]:
                    storage_hostnames.append(sthostname)
                    storage_host_password=env.passwords[entry]
                    storage_pass_list.append(storage_host_password)
                    storage_host = get_control_host_string(entry)
                    storage_data_ip=get_data_ip(storage_host)[0]
                    storage_host_list.append(storage_data_ip)
                    if new_host_entry == entry:
                        new_storage_hostnames = sthostname
        storage_master=env.roledefs['storage-master'][0]
        storage_master_ip=get_data_ip(storage_master)[0]
        storage_master_password=env.passwords[env.roledefs['storage-master'][0]]
        with  settings(host_string = storage_master, password = storage_master_password):
            with cd(INSTALLER_DIR):
                # Argument details
                # storage-setup-mode - addnode - Add a new node
                # storage-master - Storage master IP
                # storage-hostnames - hostnames of all the nodes (storage master + storage compute)
                # storage-host-tokens - password for all the nodes (storage master + storage compute)
                # storage-disk-config - Disk list for Ceph combined pool or HDD pool
                # storage-ssd-disk-config - Disk list for Ceph SSD pool
                # storage-journal-config - OSD journal disk list
                # storage-local-disk-config - Disk list for local LVM pool
                # storage-local-ssd-disk-config - Disk list for local LVM SSD pool
                # storage-local-nfs-disk-config - NFS storage list
                # storage-directory-config - Directory list for Ceph
                cmd= "PASSWORD=%s python setup-vnc-storage.py --storage-setup-mode addnode --add-storage-node %s --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-ssd-disk-config %s --storage-journal-config %s --storage-local-disk-config %s --storage-local-ssd-disk-config %s --storage-nfs-disk-config %s --storage-directory-config %s --live-migration %s" \
                        %(storage_master_password, new_storage_hostnames, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_ssd_disk_config()), ' '.join(get_storage_journal_config()), ' '.join(get_storage_local_disk_config()), ' '.join(get_storage_local_ssd_disk_config()), ' '.join(get_storage_nfs_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts())
                print cmd
                run(cmd)


@task
@EXECUTE_TASK
@roles('storage-compute')
@task
def setup_compute_storage():
    """Provisions storage compute services."""
    execute("setup_storage_compute_node", env.host_string)

@task
def setup_storage_compute_node(*args):
	"""Provisions storage compute services in one or list of nodes"""
	#dummy for now
	return

@roles('build')
@task
def unconfigure_storage():
    """UnProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "unconfigure")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "unconfigure")
#end unconfigure_storage

@roles('build')
@task
def reconfigure_storage():
    """ReProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "reconfigure")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "reconfigure")
#end reconfigure_storage

@roles('build')
@task
def setup_storage():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_master_storage", "setup")
    execute(setup_compute_storage)
    execute("setup_webui_storage", "setup")
#end setup_storage

@roles('build')
@task
def setup_nfs_livem():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "setup")
#end setup_nfs_livem

@roles('build')
@task
def setup_nfs_livem_global():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "setup_global")
#end setup_nfs_livem_global

@roles('build')
@task
def unconfigure_nfs_livem():
    """UnProvisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "unconfigure")
#end unconfigure_nfs_livem

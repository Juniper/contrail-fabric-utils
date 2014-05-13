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
@roles('storage-master')
@task
def setup_master_storage():
    """Provisions storage master services."""
    execute("setup_storage_master_node", env.host_string)

@task
def setup_storage_master_node(*args):
    """Provisions storage master services""" 
    for host_string in args:
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
            storage_master=get_control_host_string(env.roledefs['storage-master'][0])
            storage_master_ip=get_data_ip(storage_master)[0]
            storage_master_password=env.passwords[env.roledefs['storage-master'][0]]
            with  settings(host_string = storage_master, password = storage_master_password):
                with cd(INSTALLER_DIR):
                    cmd= "PASSWORD=%s python setup-vnc-storage.py --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-directory-config %s --live-migration %s" \
                            %(storage_master_password, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts())
                    print cmd
                    run(cmd)
#end setup_storage_master

@task
@EXECUTE_TASK
@roles('storage-master')
@task
def setup_nfs_live_migration():
    """Provisions nfs vm for live migration and live migration related configuration."""
    execute("setup_nfs_live_migration_services", env.host_string)

@task
def setup_nfs_live_migration_services(*args):
    """Provisions storage master services""" 
    for host_string in args:
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
            storage_master=get_control_host_string(env.roledefs['storage-master'][0])
            storage_master_ip=get_data_ip(storage_master)[0]
            storage_master_password=env.passwords[env.roledefs['storage-master'][0]]
            with  settings(host_string = storage_master, password = storage_master_password):
                with cd(INSTALLER_DIR):
                    cmd= "PASSWORD=%s python setup-vnc-livemigration.py --storage-master %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-directory-config %s --live-migration %s --nfs-live-migration %s" \
                       	%(storage_master_password, storage_master_ip, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts(), get_nfs_live_migration_opts())
                    print cmd
                    run(cmd)
#end setup_nfs_live_migration_services


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
def setup_storage():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute(setup_master_storage)
    execute(setup_compute_storage)
#end setup_storage

@roles('build')
@task
def setup_nfs_livem():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute(setup_nfs_live_migration)
#end setup_nfs_livem

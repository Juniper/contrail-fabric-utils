import os
from netaddr import *

from fabric.api import *

from fabfile.config import testbed
from fabfile.utils.host import *

def get_storage_disk_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_disk_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'disks' in storage_info[entry].keys():
                        for disk_entry in storage_info[entry]['disks']:
                            storage_disk_node = sthostname + ':' + disk_entry
                            storage_disk_node_list.append(storage_disk_node)
    if storage_disk_node_list == []:
        storage_disk_node_list.append('none')
    return (storage_disk_node_list)
#end get_storage_disk_config

def get_storage_ssd_disk_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_ssd_disk_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'ssd-disks' in storage_info[entry].keys():
                        for ssd_disk_entry in storage_info[entry]['ssd-disks']:
                            storage_ssd_disk_node = sthostname + ':' + ssd_disk_entry
                            storage_ssd_disk_node_list.append(storage_ssd_disk_node)
    if storage_ssd_disk_node_list == []:
        storage_ssd_disk_node_list.append('none')
    return (storage_ssd_disk_node_list)
#end get_storage_disk_config

def get_storage_local_disk_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_local_disk_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'local-disks' in storage_info[entry].keys():
                        for local_disk_entry in storage_info[entry]['local-disks']:
                            storage_local_disk_node = sthostname + ':' + local_disk_entry
                            storage_local_disk_node_list.append(storage_local_disk_node)
    if storage_local_disk_node_list == []:
        storage_local_disk_node_list.append('none')
    return (storage_local_disk_node_list)
#end get_storage_local_disk_config

def get_storage_local_ssd_disk_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_local_ssd_disk_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'local-ssd-disks' in storage_info[entry].keys():
                        for local_ssd_disk_entry in storage_info[entry]['local-ssd-disks']:
                            storage_local_ssd_disk_node = sthostname + ':' + local_ssd_disk_entry
                            storage_local_ssd_disk_node_list.append(storage_local_ssd_disk_node)
    if storage_local_ssd_disk_node_list == []:
        storage_local_ssd_disk_node_list.append('none')
    return (storage_local_ssd_disk_node_list)
#end get_storage_local_disk_config

def get_storage_nfs_disk_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_nfs_disk_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'nfs' in storage_info[entry].keys():
                        for nfs_disk_entry in storage_info[entry]['nfs']:
                            storage_nfs_disk_node = sthostname + ':' + nfs_disk_entry
                            storage_nfs_disk_node_list.append(storage_nfs_disk_node)
    if storage_nfs_disk_node_list == []:
        storage_nfs_disk_node_list.append('none')
    return (storage_nfs_disk_node_list)
#end get_storage_nfs_disk_config

def get_storage_journal_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_journal_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'journal' in storage_info[entry].keys():
                        for journal_entry in storage_info[entry]['journal']:
                            storage_journal_node = sthostname + ':' + journal_entry
                            storage_journal_node_list.append(storage_journal_node)
    if storage_journal_node_list == []:
        storage_journal_node_list.append('none')
    return (storage_journal_node_list)
#end get_storage_journal_config

def get_storage_directory_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_directory_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'directories' in storage_info[entry].keys():
                        for directory_entry in storage_info[entry]['directories']:
                            storage_directory_node = sthostname + ':' + directory_entry
                            storage_directory_node_list.append(storage_directory_node)
    if storage_directory_node_list == []:
        storage_directory_node_list.append('none')
    return (storage_directory_node_list)
#end get_storage_directory_config

def get_storage_chassis_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_chassis_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'chassis' in storage_info[entry].keys():
                        for chassis_entry in storage_info[entry]['chassis']:
                            storage_chassis_node = sthostname + ':' + chassis_entry
                            storage_chassis_node_list.append(storage_chassis_node)
    if storage_chassis_node_list == []:
        storage_chassis_node_list.append('none')
    return (storage_chassis_node_list)
#end get_storage_chassis_config

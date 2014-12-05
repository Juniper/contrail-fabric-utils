import os
import sys
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

# NFS config parser
# Eg., nfs configuration. This is for NFS storage support for cinder.
# Cinder can create volumes from the NFS store.
# storage_node_config = {
#   host1 : { 'disks' : ['/dev/sdd:/dev/sdc'], 'nfs' : ['11.1.0.1:/nfsvol'] },
#   host2 : { 'disks' : ['/dev/sdd:/dev/sdc'], 'nfs' : ['11.1.0.3:/nfsvol'] },
#   host3 : { 'disks' : ['/dev/sdb:/dev/sdf'] },
#   host4 : { 'disks' : ['/dev/sdd:/dev/sdc'] },
# }
# The function will parse the above config and returns
# the list '11.1.0.1:/nfsvol' '11.1.0.3:/nfsvol'
# Note: The host entry is not needed.
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
                            storage_nfs_disk_node = nfs_disk_entry
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

# Chassis config parser
# Eg., chassis configuration. This has to be provided when more than one
# node is part of a single chassis. This will avoid replication of data
# between nodes in the same chassis to avoid data loss when chassis goes
# down
# storage_node_config = {
#   host1 : { 'disks' : ['/dev/sdd:/dev/sdc'], 'chassis' : ['T0'] },
#   host2 : { 'disks' : ['/dev/sdd:/dev/sdc'], 'chassis' : ['T0'] },
#   host3 : { 'disks' : ['/dev/sdb:/dev/sdf'], 'chassis' : ['T1'] },
#   host4 : { 'disks' : ['/dev/sdd:/dev/sdc'], 'chassis' : ['T1'] },
# }
# The function will parse the above config and returns
# the list 'host1:T0 host2:T0 host3:T1 host4:T1'

def get_storage_chassis_config():
    storage_info = getattr(testbed, 'storage_node_config', None)
    storage_chassis_node_list=[]
    if storage_info:
        for entry in storage_info.keys():
            storage_host = get_control_host_string(entry)
            added_chassis = 0
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    if 'chassis' in storage_info[entry].keys():
                        for chassis_entry in storage_info[entry]['chassis']:
                            if added_chassis != 0:
                                print 'More than one chassis id configured for host %s' %(sthostname)
                                sys.exit(0)
                            added_chassis = 1

                            storage_chassis_node = sthostname + ':' + chassis_entry
                            storage_chassis_node_list.append(storage_chassis_node)
    if storage_chassis_node_list == []:
        storage_chassis_node_list.append('none')
    return (storage_chassis_node_list)
#end get_storage_chassis_config

def get_from_testbed_dict( dictionary, key,default_value):
    try:
        val = env[dictionary][key]
    except KeyError:
        val = default_value
    return val

def get_cinder_ha_vip():
    ha_vip = get_from_testbed_dict('ha', 'internal_vip', None)
    if ha_vip:
        return ha_vip
    return 'none'
#end get_cinder_ha_vip


# storage host with monitors config
def get_storage_mon_hosts():
    storage_mon_info = getattr(testbed, 'storage_compute_mon_list', None)
    storage_mon_list = []
    if storage_mon_info:
        for entry in storage_mon_info:
            storage_host = get_control_host_string(entry)
            for sthostname, sthostentry in zip(env.hostnames['all'], env.roledefs['all']):
                if entry == sthostentry:
                    storage_mon_list.append(sthostname)
    if storage_mon_list == []:
        storage_mon_list.append('none')
    return (storage_mon_list)
#end get_storage_mon_hosts config

def get_cfg_ha_vip():
    ha_vip = get_from_testbed_dict('ha', 'contrail_internal_vip', None)
    if ha_vip:
        return ha_vip
    return 'none'

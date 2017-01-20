import json

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.utils.migration import *
from fabfile.utils.storage import *
from fabfile.utils.analytics import *
from fabfile.utils.cluster import get_all_hostnames

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
    storage_webui_host_password = get_env_passwords(host_string)

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
             cmds = ["PASSWORD=%s" % storage_webui_host_password,
                     "setup-vnc-storage-webui",
                     "--storage-setup-mode %s" % mode,
                     "--storage-webui-ip %s" % storage_webui_ip,
                     "--storage-rest-ip %s" % storage_rest_ip,
                     "--storage-disk-config %s" % ' '.join(get_storage_disk_config()),
                     "--storage-ssd-disk-config %s" % ' '.join(get_storage_ssd_disk_config())]
             cmd = ' '.join(cmds)
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
    orig_hostnames=[]
    collector_pass_list=[]
    collector_host_list=[]
    cfg_host_list=[]
    storage_os_pass_list=[]
    storage_os_host_list=[]
    storage_compute_hostnames=[]
    openstack_ip = ''
    storage_network = False
    index = 0
    data_ip_info = getattr(testbed, 'storage_data', None)
    if data_ip_info != None:
        storage_network = True
    for entry in env.roledefs['storage-master']:
        for sthostname, sthostentry in zip(get_all_hostnames(),
                                                env.roledefs['all']):
            if entry == sthostentry:
                if storage_network == True:
                    storage_hostnames.append('%s-storage' %(sthostname))
                else:
                    storage_hostnames.append(sthostname)
                orig_hostnames.append(sthostname)
                storage_host_password=get_env_passwords(entry)
                storage_pass_list.append(storage_host_password)
                storage_data_ip=get_storage_data_ip(entry)[0]
                storage_host_list.append(storage_data_ip)
                if index != 0:
                    storage_os_pass_list.append(storage_host_password)
                    storage_os_host_list.append(storage_data_ip)
                index = index + 1
    for entry in env.roledefs['storage-compute']:
        for sthostname, sthostentry in zip(get_all_hostnames(),
                                                env.roledefs['all']):
            for exist_name in orig_hostnames:
                if sthostname == exist_name:
                    break
            if exist_name == sthostname:
                continue
            if entry == sthostentry:
                if storage_network == True:
                    storage_compute_hostnames.append('%s-storage' %(sthostname))
                else:
                    storage_compute_hostnames.append(sthostname)

            if entry == sthostentry and \
                            entry != env.roledefs['storage-master'][0]:
                if storage_network == True:
                    storage_hostnames.append('%s-storage' %(sthostname))
                else:
                    storage_hostnames.append(sthostname)
                orig_hostnames.append(sthostname)
                storage_host_password=get_env_passwords(entry)
                storage_pass_list.append(storage_host_password)
                storage_data_ip=get_storage_data_ip(entry)[0]
                storage_host_list.append(storage_data_ip)
    for entry in env.roledefs['collector']:
        for sthostname, sthostentry in zip(get_all_hostnames(),
                                                env.roledefs['all']):
            if entry == sthostentry:
                collector_pass_list.append(get_env_passwords(entry))
                collector_host = get_control_host_string(entry)
                collector_data_ip=get_data_ip(collector_host)[0]
                collector_host_list.append(collector_data_ip)
    index = 0
    for entry in env.roledefs['cfgm']:
        for sthostname, sthostentry in zip(get_all_hostnames(),
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
    storage_master_ip=get_storage_data_ip(storage_master)[0]
    openstack_ip = get_data_ip(storage_master)[0]
    cfm = env.roledefs['cfgm'][0]
    cfm_ip = get_data_ip(cfm)[0]
    storage_master_password=get_env_passwords(env.roledefs['storage-master'][0])
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
    # storage-replica-size - Replica size for Ceph storage
    # openstack-ip - IP address of the first openstack node
    # orig-hostnames - Original hostnames
    # service-dbpass - DB password for cinder(and all service) db user
    # region-name - Region name for keystone services
    # ssd-cache-tier - Enable/Disable SSD cache tier
    # object-storage - Enable/Disable Ceph Object storage
    # object-storage-pool - pool to use for object storage.
    # WARNING: If anything is added in the arguments, make sure it
    # doesn't break add_storage_node task.
    cmds = ["PASSWORD=%s" % storage_master_password, "setup-vnc-storage",
            "--storage-setup-mode %s" % mode,
            "--storage-master %s" % storage_master_ip,
            "--storage-hostnames %s" % ' '.join(storage_hostnames),
            "--storage-hosts %s" % ' '.join(storage_host_list),
            "--storage-host-tokens %s" % ' '.join(storage_pass_list),
            "--storage-disk-config %s" % ' '.join(get_storage_disk_config()),
            "--storage-ssd-disk-config %s" % ' '.join(get_storage_ssd_disk_config()),
            "--storage-journal-config %s" % ' '.join(get_storage_journal_config()),
            "--storage-local-disk-config %s" % ' '.join(get_storage_local_disk_config()),
            "--storage-local-ssd-disk-config %s" % ' '.join(get_storage_local_ssd_disk_config()),
            "--storage-nfs-disk-config %s" % ' '.join(get_storage_nfs_disk_config()),
            "--storage-directory-config %s" % ' '.join(get_storage_directory_config()),
            "--storage-chassis-config %s" % ' '.join(get_storage_chassis_config()),
            "--live-migration %s" % get_live_migration_opts(),
            "--collector-hosts %s" % ' '.join(collector_host_list),
            "--collector-host-tokens %s" % ' '.join(collector_pass_list),
            "--cfg-host %s" % cfm_ip,
            "--cinder-vip %s" % get_cinder_ha_vip(),
            "--config-hosts %s" % ' '.join(cfg_host_list),
            "--storage-os-hosts %s" % ' '.join(storage_os_host_list),
            "--storage-os-host-tokens %s" % ' '.join(storage_os_pass_list),
            "--storage-mon-hosts %s" % ' '.join(get_storage_mon_hosts()),
            "--cfg-vip %s" % get_cfg_ha_vip(),
            "--storage-compute-hostnames %s" % ' '.join(storage_compute_hostnames),
            "--storage-replica-size %s" % get_storage_replica_size(),
            "--openstack-ip %s" % openstack_ip,
            "--orig-hostnames %s" % ' '.join(orig_hostnames),
            "--service-dbpass %s" % get_service_dbpass(),
            "--region-name %s" % get_region_name(),
            "--ssd-cache-tier %s" % get_storage_cache_tier(),
            "--object-storage %s" % get_object_storage(),
            "--object-storage-pool %s" % get_object_storage_pool()]
    cmd = ' '.join(cmds)
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
@roles('openstack')
def setup_nfs_live_migration(mode):
    """Provisions nfs vm for live migration and live migration related configuration."""
    host_string = env.host_string
    if host_string == env.roledefs['openstack'][0]:
        storage_host_entries=[]
        storage_pass_list=[]
        storage_host_list=[]
        storage_hostnames=[]
        storage_os_pass_list=[]
        storage_os_host_list=[]
        index = 0
        for entry in env.roledefs['compute']:
            for sthostname, sthostentry in zip(get_all_hostnames(), env.roledefs['all']):
                if entry == sthostentry:
                    #Add only for qemu-kvm hypervisor
                    hypervisor = get_hypervisor(entry)
                    if hypervisor != 'libvirt' and hypervisor != 'qemu' and \
                            hypervisor != 'kvm' and hypervisor != 'qemu-kvm':
                        continue
                    storage_hostnames.append(sthostname)
                    storage_host_password=get_env_passwords(entry)
                    storage_pass_list.append(storage_host_password)
                    storage_host = get_control_host_string(entry)
                    storage_data_ip=get_data_ip(storage_host)[0]
                    storage_host_list.append(storage_data_ip)

        storage_master=env.roledefs['openstack'][0]
        storage_master_ip=get_data_ip(storage_master)[0]
        storage_master_password=get_env_passwords(env.roledefs['openstack'][0])
        cfm = env.roledefs['cfgm'][0]
        cfm_ip = get_data_ip(cfm)[0]

        live_migration_scope = get_live_migration_scope()
        # if mode is 'setup_lm', just setup openstack nova live-migration
        # configuration alone. Ignore all NFS live-migration settings from
        # testbed.py.
        if mode == 'setup_lm':
            mode = 'setup'
            no_nfs = 1
        else:
            no_nfs = 0
            if mode == 'setup_global':
                live_migration_scope = 'enabled'
            else:
                if live_migration_scope == 'global' and mode == 'setup':
                    mode = 'setup_global'

        for entry in env.roledefs['openstack']:
            for sthostname, sthostentry in zip(get_all_hostnames(),
                                                    env.roledefs['all']):
                if entry == sthostentry:
                    storage_host_password=get_env_passwords(entry)
                    storage_host = get_control_host_string(entry)
                    storage_data_ip=get_data_ip(storage_host)[0]
                    if index != 0:
                        storage_os_pass_list.append(storage_host_password)
                        storage_os_host_list.append(storage_data_ip)
                    index = index + 1

        if storage_os_host_list == []:
            storage_os_host_list.append('none')

        if storage_os_pass_list == []:
            storage_os_pass_list.append('none')

        if storage_master_ip != cfm_ip:
            with  settings(host_string = storage_master, password = storage_master_password):
                if no_nfs == 0 and get_ext_nfs_migration_enable() != True:
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
                # storage-os-hosts - storage openstack hosts (except storage-master)
                # storage-os-host-tokens - storage openstack hosts passwd list
                cmd= "PASSWORD=%s setup-vnc-livemigration --storage-setup-mode %s --storage-master %s --storage-master-token %s --storage-hostnames %s --storage-hosts %s --storage-host-tokens %s --storage-disk-config %s --storage-directory-config %s --live-migration %s --nfs-live-migration %s  --storage-os-hosts %s --storage-os-host-tokens %s --fix-nova-uid %s --live-migration-scope %s" \
                    %(storage_master_password, mode, storage_master_ip, storage_master_password, ' '.join(storage_hostnames), ' '.join(storage_host_list), ' '.join(storage_pass_list), ' '.join(get_storage_disk_config()), ' '.join(get_storage_directory_config()), get_live_migration_opts(), get_nfs_live_migration_opts(no_nfs), ' '.join(storage_os_host_list), ' '.join(storage_os_pass_list), get_nova_uid_fix_opt(), live_migration_scope)
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

# base openstack nova live-migration configuration
@task
@roles('build')
def setup_livemigration():
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute("setup_nfs_live_migration", "setup_lm")
#end setup_livemigration

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

@task
@roles('build')
def setup_storage_interface():
    '''
    Configure the IP address, netmask, gateway and vlan information
    based on parameter passed in 'control_data' stanza of testbed file.
    Also generate ifcfg file for the interface if the file is not present.
    '''
    execute('setup_storage_interface_node')
#end setup_storage_interface_node

@task
def setup_storage_interface_node(*args):
    '''
    Configure the IP address, netmask, gateway and vlan information
    in one or list of nodes based on parameter passed to this task.
    '''
    hosts = getattr(testbed, 'storage_data', None)
    if not hosts:
        print 'WARNING: \'storage_data\' block is not defined in testbed file.',\
              'Skipping setup-interface...'
        return
    # setup interface for only the required nodes.
    if args:
        for host in args:
            if host not in hosts.keys():
                print "\n\n*** WARNING: storage_data interface details for host " +\
                      "%s not defined in testbed file. Skipping! ***\n\n" % host
        hosts = dict((key, val) for (key, val) in
                     getattr(testbed, 'storage_data', None).items()
                     if key in args)
    bondinfo = getattr(testbed, 'bond', None)

    retries = 5; timeout = 5
    for host in hosts.keys():
        cmd = 'setup-vnc-interfaces'
        errmsg = 'WARNING: Host ({HOST}) is defined with device ({DEVICE})'+\
                 ' but its bond info is not available\n'
        if hosts[host].has_key('device') and hosts[host].has_key('ip'):
            cmd += ' --device {device} --ip {ip}'.format(**hosts[host])
            device = hosts[host]['device']
            if 'bond' in device.lower():
                if not bondinfo or not (bondinfo.has_key(host)
                    and device == bondinfo[host]['name']):
                    print (errmsg.format(HOST=host,
                                           DEVICE=hosts[host]['device']))
                    continue
                if not bondinfo[host].has_key('member'):
                    raise AttributeError('Bond members are not defined for'+ \
                                         ' host %s, device %s' %(host, device))
                bond_members = " ".join(bondinfo[host]['member'])
                del bondinfo[host]['member']; del bondinfo[host]['name']
                cmd += ' --members %s --bond-opts \'%s\''%(bond_members,
                                             json.dumps(bondinfo[host]))
            if hosts[host].has_key('vlan'):
                cmd += ' --vlan %s' %hosts[host]['vlan']
            if (get_storage_host_string(host) == host) and hosts[host].has_key('gw'):
                cmd += ' --gw %s' %hosts[host]['gw']
            with settings(host_string= host,
                          timeout= timeout,
                          connection_attempts= retries):
                with cd(INSTALLER_DIR):
                    sudo(cmd)
        else:
            raise AttributeError("'device' or 'ip' is not defined for %s" %host)
# end setup_storage_interface_node

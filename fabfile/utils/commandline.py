from fabric.api import env, sudo

from host import *
from cluster import *
from analytics import *
from interface import *
from multitenancy import *
from fabfile.tasks.esxi_defaults import apply_esxi_defaults

def get_config_db_ip_list():
    role = 'database'
    if manage_config_db():
        role = 'cfgm'
    return [hstr_to_ip(get_control_host_string(config_db_host))
            for config_db_host in env.roledefs[role]]

def frame_vnc_database_cmd(host_string, cmd="setup-vnc-database"):
    parent_cmd = cmd
    database_host = host_string
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    database_host_list = [get_control_host_string(entry)\
                          for entry in env.roledefs['database']]
    database_ip_list = [hstr_to_ip(db_host) for db_host in database_host_list]
    zookeeper_ip_list = [hstr_to_ip(get_control_host_string(config_host))\
                                    for config_host in env.roledefs['cfgm']]
    collector_ip_list = [hstr_to_ip(get_control_host_string(config_host))\
                                    for config_host in env.roledefs['collector']]
    database_host=get_control_host_string(host_string)
    database_host_password=get_env_passwords(host_string)
    tgt_ip = hstr_to_ip(database_host)
    opscenter_ip = hstr_to_ip(env.roledefs['webui'][0])

    if parent_cmd != "remove-cassandra-node" and parent_cmd != 'decommission-cassandra-node':
        #derive kafka broker id from the list of servers specified
        broker_id = sorted(database_ip_list).index(tgt_ip)
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    cmd += " --self_ip %s" % tgt_ip
    cmd += " --cfgm_ip %s" % cfgm_ip
    cmd += " --opscenter_ip %s" % opscenter_ip

    database_dir = get_database_dir()
    if database_dir is not None:
        cmd += " --data_dir %s" % database_dir
    analytics_data_dir = get_analytics_data_dir()
    if analytics_data_dir is not None:
        cmd += " --analytics_data_dir %s" % analytics_data_dir
    ssd_data_dir = get_ssd_data_dir()
    if ssd_data_dir is not None:
        cmd += " --ssd_data_dir %s" % ssd_data_dir
    if (len(env.roledefs['database'])>2):
        cmd += " --seed_list %s" % ','.join(database_ip_list[:2])
    else:
        cmd += " --seed_list %s" % (hstr_to_ip(get_control_host_string(
                                       env.roledefs['database'][0])))
    cmd += " --zookeeper_ip_list %s" % ' '.join(zookeeper_ip_list)
    cmd += " --collector_ip_list %s" % ' '.join(collector_ip_list)
    if parent_cmd in ['setup-vnc-database',
                      'update-zoo-servers',
                      'upgrade-vnc-database']:
        cmd += " --database_index %d" % (database_host_list.index(database_host) + 1)
    minimum_diskGB = get_minimum_diskGB()
    if minimum_diskGB is not None:
        cmd += " --minimum_diskGB %s" % minimum_diskGB
    if (parent_cmd in ['setup-vnc-database', 'upgrade-vnc-database']
            and get_kafka_enabled() is not None):
        cmd += " --kafka_broker_id %d" % broker_id
    if parent_cmd == "remove-cassandra-node":
        cmd += " --node_to_delete %s" % hstr_to_ip(host_string)

    if cassandra_user is not None:
        cmd += " --cassandra_user %s" % cassandra_user
        cmd += " --cassandra_password %s" % cassandra_password

    return cmd

def frame_vnc_openstack_cmd(host_string, cmd="setup-vnc-openstack"):
    amqp_server_ip = get_openstack_amqp_server()
    self_host = get_control_host_string(host_string)
    self_ip = hstr_to_ip(self_host)
    mgmt_self_ip = hstr_to_ip(host_string)
    openstack_host_password = get_env_passwords(host_string)
    authserver_ip = get_authserver_ip(ignore_vip=True,
                                  openstack_node=host_string)
    (_, openstack_admin_password) = get_authserver_credentials()
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = hstr_to_ip(cfgm_host)
    internal_vip = get_openstack_internal_vip()

    cmd += " --self_ip %s" % self_ip
    cmd += " --keystone_ip %s" % authserver_ip
    cmd += " --keystone_version %s" % get_keystone_version()
    cmd += " --keystone_admin_passwd %s" % openstack_admin_password
    cmd += " --cfgm_ip %s " % cfgm_ip
    cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
    cmd += " --amqp_server_ip %s" % amqp_server_ip
    cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
    cmd += " --service_token %s" % get_service_token()
    cmd += " --service-dbpass %s" % get_service_dbpass()
    cmd += " --keystone_service_tenant_name %s" % get_keystone_service_tenant_name()
    cmd += " --region_name %s" % get_region_name()
    cmd += " --neutron_password %s" % get_neutron_password()
    cmd += " --nova_password %s" % get_nova_password()
    cmd += " --openstack_index %s" % (env.roledefs['openstack'].index(
                                          host_string) + 1)
    if keystone_ssl_enabled():
        cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
        cmd += " --keystone_certfile %s" % get_keystone_certfile()
        cmd += " --keystone_keyfile %s" % get_keystone_keyfile()
        cmd += " --keystone_cafile %s" % get_keystone_cafile()
    haproxy = get_haproxy()
    if haproxy:
        cmd += " --haproxy %s" % haproxy
    openstack_ip_list = []
    if internal_vip:
        # Highly available setup
        openstack_ip_list = ' '.join([hstr_to_ip(openstack_host)
                            for openstack_host in env.roledefs['openstack']])
        cmd += ' --internal_vip %s' % (internal_vip)
        cmd += ' --mgmt_self_ip %s' % mgmt_self_ip
    contrail_internal_vip = get_contrail_internal_vip()
    if contrail_internal_vip:
        # Highly available setup with multiple interface
        cmd += ' --contrail_internal_vip %s' % (contrail_internal_vip)
    if openstack_ip_list:
        cmd += ' --openstack_ip_list %s' % openstack_ip_list

    osapi_compute_workers, conductor_workers = get_nova_workers()
    if osapi_compute_workers:
        cmd += ' --osapi_compute_workers %s' % osapi_compute_workers
    if conductor_workers:
        cmd += ' --conductor_workers %s' % conductor_workers

    sriov_enabled = get_sriov_enabled()
    if sriov_enabled:
        cmd += ' --sriov'

    return cmd

def frame_vnc_config_cmd(host_string, cmd="setup-vnc-config"):
    nworkers = 1
    quantum_port = '9697'
    cfgm_host=get_control_host_string(host_string)
    tgt_ip = hstr_to_ip(cfgm_host)

    # Prefer local collector node
    cfgm_host_list = [get_control_host_string(entry)\
                     for entry in env.roledefs['cfgm']]
    collector_host_list = [get_control_host_string(entry)\
                          for entry in env.roledefs['collector']]
    collector_ip = None
    if cfgm_host in collector_host_list:
        collector_ip = tgt_ip
    else:
        # Select based on index
        hindex = cfgm_host_list.index(cfgm_host)
        hindex = hindex % len(env.roledefs['collector'])
        collector_host = get_control_host_string(
                             env.roledefs['collector'][hindex])
        collector_ip = hstr_to_ip(collector_host)

    collector_ip_list = [hstr_to_ip(get_control_host_string(entry))\
                          for entry in collector_host_list]
    zookeeper_ip_list = [hstr_to_ip(get_control_host_string(config_host))\
                         for config_host in env.roledefs['cfgm']]
    control_ip_list = []
    if 'control' in env.roledefs:
        control_ip_list = [hstr_to_ip(get_control_host_string(control_host))\
                          for control_host in env.roledefs['control']]

    orch = get_orchestrator()
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    cmd += " --self_ip %s" % tgt_ip
    cmd += " --cfgm_index %d" % (cfgm_host_list.index(cfgm_host) + 1)
    cmd += " --collector_ip %s" % (collector_ip)
    cmd += " --collector_ip_list %s" % ' '.join(collector_ip_list)
    cmd += " --cassandra_ip_list %s" % ' '.join(get_config_db_ip_list())
    cmd += " --zookeeper_ip_list %s" % ' '.join(zookeeper_ip_list)
    if control_ip_list:
        cmd += " --control_ip_list %s" % ' '.join(control_ip_list)
    cmd += " --quantum_port %s" % quantum_port
    cmd += " --nworkers %d" % nworkers
    cmd += " --service_token %s" % get_service_token()
    cmd += " --amqp_ip_list %s" % ' '.join(get_amqp_servers())
    cmd += " --amqp_port %s" % get_amqp_port()
    amqp_password = get_amqp_password()
    if amqp_password:
        cmd += " --amqp_password %s" % amqp_password
    if apiserver_ssl_enabled():
        cmd += " --apiserver_insecure %s" % get_apiserver_insecure_flag()
        cmd += " --apiserver_certfile %s" % get_apiserver_certfile()
        cmd += " --apiserver_keyfile %s" % get_apiserver_keyfile()
        cmd += " --apiserver_cafile %s" % get_apiserver_cafile()
        first_cfgm_ip = hstr_to_ip(cfgm_host_list[0])
        cmd += " --first_cfgm_ip %s" % first_cfgm_ip
    cmd += " --orchestrator %s" % orch
    if (len(env.roledefs['cfgm'])>2):
        cmd += " --seed_list %s" % ','.join(get_config_db_ip_list()[:2])
    else:
        cmd += " --seed_list %s" % ','.join(get_config_db_ip_list())
    database_dir = get_database_dir() or '/var/lib/cassandra/data'
    cmd += " --data_dir %s" % database_dir
    haproxy = get_haproxy()
    if haproxy:
        cmd += " --haproxy %s" % haproxy
    if manage_config_db():
        cmd += " --manage_db"
    cmd += get_rbac_opts()
    if orch == 'openstack':
        (_, openstack_admin_password) = get_authserver_credentials()
        authserver_ip = get_authserver_ip()
        # Pass keystone arguments in case for openstack orchestrator
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --keystone_version %s" % get_keystone_version()
        cmd += " --keystone_admin_passwd %s" % openstack_admin_password
        cmd += " --keystone_service_tenant_name %s" % get_keystone_service_tenant_name()
        cmd += ' --neutron_password %s' % get_neutron_password()
        cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
        cmd += " --keystone_auth_port %s" % get_authserver_port()
        cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
        if keystone_ssl_enabled():
            cmd += " --keystone_certfile %s" % get_keystone_certfile()
            cmd += " --keystone_keyfile %s" % get_keystone_keyfile()
            cmd += " --keystone_cafile %s" % get_keystone_cafile()
        cmd += " --region_name %s" % get_region_name()
        manage_neutron = get_manage_neutron()
        if manage_neutron == 'no':
            # Skip creating neutron service tenant/user/role etc in keystone.
            cmd += ' --manage_neutron %s' % manage_neutron
        provision_neutron_server = get_provision_neutron_server()
        if provision_neutron_server == 'no':
            # Skip configuring/running neutron service in cfgm node
            cmd += ' --provision_neutron_server %s' % provision_neutron_server

    else:
        cmd += ' --manage_neutron no'
    internal_vip = get_openstack_internal_vip()
    contrail_internal_vip = get_contrail_internal_vip()
    if internal_vip:
        # Highly available openstack setup
        cmd += ' --internal_vip %s' % (internal_vip)
    elif get_orchestrator() == 'openstack':
        openstack_ctrl_ip = hstr_to_ip(get_control_host_string(env.roledefs['openstack'][0]))
        cmd += ' --openstack_ctrl_ip %s' % (openstack_ctrl_ip)
    if contrail_internal_vip:
        # Highly available contrail setup
        cmd += ' --contrail_internal_vip %s' % (contrail_internal_vip)
    if cassandra_user is not None:
        cmd += ' --cassandra_user %s' % (cassandra_user)
        cmd += ' --cassandra_password %s' % (cassandra_password)
    cloud_admin_role = get_cloud_admin_role()
    if cloud_admin_role:
        cmd += " --cloud_admin_role %s" % cloud_admin_role
    return cmd

def frame_vnc_vcenter_plugin_cmd(host_string, cmd="setup-vcenter-plugin"):
    # Frame the command  to provision vcenter-plugin
    vcenter_info = getattr(env, 'vcenter_servers', None)
    if not vcenter_info:
        print 'Error: vcenter block is not defined in testbed file.Exiting'
        return
    else:
        for v in vcenter_info.keys():
             if get_orchestrator() == 'vcenter':
                 vcenter_server = vcenter_info[v]
                 datacenters = get_vcenter_datacenters(vcenter_server)
                 for dc in datacenters:
                      datacenter = dc
                      dc_info = vcenter_server['datacenters'][dc]
                      for dvs in dc_info['dv_switches'].keys():
                           dv_switch = dvs
                           break
                      break
                 break
             else:
                 vcenter_server = vcenter_info[v]
                 datacenters = get_vcenter_datacenters(vcenter_server)
                 for dc in datacenters:
                     dc_info = vcenter_server['datacenters'][dc]
                     vcenter_compute_nodes = get_vcenter_compute_nodes(dc_info)
                     if host_string.split('@')[1] in vcenter_compute_nodes:
                         vcenter_server = vcenter_info[v]
                         datacenter = dc
                         for dvs in dc_info['dv_switches'].keys():
                             dvs_info = dc_info['dv_switches'][dvs]
                             if host_string.split('@')[1] == dvs_info['vcenter_compute']:
                                 dv_switch = dvs
                                 break

    zookeeper_ip_list = [hstr_to_ip(get_control_host_string(config_host))
            for config_host in env.roledefs['cfgm']]
    if get_orchestrator() == 'vcenter':
        cfgm_ip = get_contrail_internal_vip() or\
          hstr_to_ip(get_control_host_string(host_string));
    else:
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    cmd += " --vcenter_url %s" % vcenter_server['server']
    cmd += " --vcenter_username %s" % vcenter_server['username']
    cmd += " --vcenter_password %s" % vcenter_server['password']
    cmd += " --vcenter_datacenter %s" % datacenter
    cmd += " --vcenter_dvswitch %s" % dv_switch
    if 'ipfabricpg' in vcenter_server.keys():
        cmd += " --vcenter_ipfabricpg %s" % vcenter_server['ipfabricpg']
    else:
        # If unspecified, set it to default value
        cmd += " --vcenter_ipfabricpg contrail-fab-pg"
    cmd += " --api_hostname %s" % cfgm_ip
    cmd += " --api_port 8082"
    zk_servers_ports = ','.join(['%s:2181' %(s) for s in zookeeper_ip_list])
    cmd += " --zookeeper_serverlist %s" % zk_servers_ports
    if 'vcenter_compute' in env.roledefs:
         cmd += " --vcenter_mode vcenter-as-compute"
         # Pass keystone arguments in case of vcenter-as-compute mode
         authserver_ip = get_authserver_ip()
         ks_admin_user, ks_admin_password = get_authserver_credentials()
         cmd += " --keystone_ip %s" % authserver_ip
         cmd += " --keystone_version %s" % get_keystone_version()
         cmd += " --keystone_admin_user %s" % ks_admin_user
         cmd += " --keystone_admin_passwd %s" % ks_admin_password
         cmd += " --keystone_admin_tenant_name %s" % get_admin_tenant_name()
         cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
         cmd += " --keystone_auth_port %s" % get_authserver_port()
    else:
         cmd += " --vcenter_mode vcenter-only"

    return cmd

def frame_vnc_webui_cmd(host_string, cmd="setup-vnc-webui"):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = hstr_to_ip(cfgm_host)
    webui_host = get_control_host_string(host_string)
    ncollectors = len(env.roledefs['collector'])
    webui_host_list=[]
    for entry in env.roledefs['webui']:
        webui_host_list.append(get_control_host_string(entry))
    # Prefer local collector node
    if webui_host in env.roledefs['collector']:
        collector_ip = hstr_to_ip(webui_host)
    else:
        # Select based on index
        hindex = webui_host_list.index(webui_host)
        hindex = hindex % ncollectors
        collector_host = get_control_host_string(env.roledefs['collector'][hindex])
        collector_ip = hstr_to_ip(collector_host)

    cfgm_host_list=[]
    for entry in env.roledefs['cfgm']:
        cfgm_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    collector_host_list=[]
    for entry in env.roledefs['collector']:
        collector_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    controller_host_list=[]
    for entry in env.roledefs['control']:
        controller_host_list.append(hstr_to_ip(get_control_host_string(entry)))

    orch = get_orchestrator()

    # If redis password is specified in testbed file, then add that to the
    # redis config file
    redis_password = get_redis_password()

    cmd += " --cfgm_ip %s" % cfgm_ip
    cmd += " --apiserver_auth_protocol %s" % get_apiserver_protocol()
    cmd += " --collector_ip %s" % collector_ip
    cmd += " --cassandra_ip_list %s" % ' '.join(get_config_db_ip_list())
    cmd += " --cfgm_ip_list %s" % ' '.join(cfgm_host_list)
    cmd += " --collector_ip_list %s" % ' '.join(collector_host_list)
    cmd += " --dns_server_ip_list %s" % ' '.join(controller_host_list)

    cmd += " --orchestrator %s" % orch
    if redis_password is not None:
        cmd += " --redis_password %s" % redis_password
    internal_vip = get_openstack_internal_vip()
    if internal_vip:
        # Highly available setup
        cmd += " --internal_vip %s" % internal_vip
    contrail_internal_vip = get_contrail_internal_vip()
    if contrail_internal_vip:
        # Highly available setup with multiple interfaces
        cmd += " --contrail_internal_vip %s" % contrail_internal_vip

    if orch == 'openstack':
        if 'openstack' in env.roledefs and len(env.roledefs['openstack']) > 0:
            openstack_host = get_control_host_string(env.roledefs['openstack'][0])
            openstack_ip = hstr_to_ip(openstack_host)
            cmd += " --openstack_ip %s" % openstack_ip
        authserver_ip = get_authserver_ip()
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
        cmd += " --keystone_version %s" % get_keystone_version()
        cmd += " --admin_user %s" % ks_admin_user
        cmd += " --admin_password %s" % ks_admin_password
        cmd += " --admin_tenant_name %s" % get_admin_tenant_name()
    elif orch == 'vcenter':
        vcenter_info = getattr(env, 'vcenter_servers', None)
        if not vcenter_info:
            print 'Error: vcenter block is not defined in testbed file.Exiting'
            return
        else:
           for v in vcenter_info:
                vcenter_server = vcenter_info[v]
                datacenters = get_vcenter_datacenters(vcenter_server)
                for dc in datacenters:
                      datacenter = dc
                      dc_info = vcenter_server['datacenters'][dc]
                      for dvs in dc_info['dv_switches'].keys():
                           dv_switch = dvs
                           break
                      break
                break
        # vcenter provisioning parameters
        cmd += " --vcenter_ip %s" % vcenter_server['server']
        cmd += " --vcenter_port %s" % vcenter_server['port']
        cmd += " --vcenter_auth %s" % vcenter_server['auth']
        cmd += " --vcenter_datacenter %s" % datacenter
        cmd += " --vcenter_dvswitch %s" % dv_switch

    return cmd

def frame_vnc_control_cmd(host_string, cmd='setup-vnc-control'):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    control_host = get_control_host_string(host_string)
    tgt_ip = hstr_to_ip(control_host)
    config_host_list=[]
    for entry in env.roledefs['cfgm']:
        config_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    collector_host_list=[]
    for entry in env.roledefs['collector']:
        collector_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    control_host_list=[]
    for entry in env.roledefs['control']:
        control_host_list.append(get_control_host_string(entry))
    cmd += ' --self_ip %s' % tgt_ip
    cmd += ' --cfgm_ip %s' % cfgm_ip
    cmd += ' --collectors %s' % ' '.join(collector_host_list)
    cmd += ' --rabbit_server_list %s' % ' '.join(get_amqp_servers())
    cmd += ' --config_db_list %s' % ' '.join(get_config_db_ip_list())

    return cmd

def frame_vnc_compute_cmd(host_string, cmd='setup-vnc-compute',
                          manage_nova_compute='yes', configure_nova='yes'):
    orch = get_orchestrator()
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
    cfgm_passwd = get_env_passwords(env.roledefs['cfgm'][0])
    compute_host = get_control_host_string(host_string)
    (tgt_ip, tgt_gw) = get_data_ip(host_string)
    metadata_secret = get_metadata_secret()

    compute_mgmt_ip= host_string.split('@')[1]
    compute_control_ip= hstr_to_ip(compute_host)

    amqp_server_ip = get_contrail_amqp_server()
    # Using amqp running in openstack node
    if (get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes' or
        get_from_testbed_dict('openstack', 'amqp_host', None)):
        amqp_server_ip = get_openstack_amqp_server()
    cpu_mode = get_nova_cpu_mode()
    cpu_model = get_nova_cpu_model()

    # Frame the command line to provision compute node.
    cmd += " --self_ip %s" % compute_control_ip
    cmd += " --cfgm_ip %s" % cfgm_ip
    cmd += " --cfgm_user %s" % cfgm_user
    cmd += " --cfgm_passwd %s" % cfgm_passwd
    cmd += " --amqp_server_ip %s" % amqp_server_ip
    cmd += " --service_token %s" % get_service_token()
    cmd += " --orchestrator %s" % get_orchestrator()
    cmd += " --hypervisor %s" % get_hypervisor(host_string)
    collector_host_list=[]
    for entry in env.roledefs['collector']:
        collector_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    cmd += ' --collectors %s' % ' '.join(collector_host_list)
    control_host_list=[]
    for entry in env.roledefs['control']:
        control_host_list.append(hstr_to_ip(get_control_host_string(entry)))
    cmd += ' --control-nodes %s' % ' '.join(control_host_list)

    haproxy = get_haproxy()
    if haproxy:
        cmd += " --haproxy %s" % haproxy

    if tgt_ip != compute_mgmt_ip:
        cmd += " --non_mgmt_ip %s" % tgt_ip
        cmd += " --non_mgmt_gw %s" % tgt_gw

    if orch == 'openstack':
        openstack_mgmt_ip = hstr_to_ip(env.roledefs['openstack'][0])
        openstack_ctrl_ip = hstr_to_ip(get_control_host_string(env.roledefs['openstack'][0]))
        authserver_ip = get_authserver_ip()
        ks_auth_protocol = get_authserver_protocol()
        ks_auth_port = get_authserver_port()
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --keystone_version %s" % get_keystone_version()
        cmd += " --openstack_mgmt_ip %s" % openstack_mgmt_ip
        cmd += " --openstack_ctrl_ip %s" % openstack_ctrl_ip
        cmd += " --keystone_auth_protocol %s" % ks_auth_protocol
        cmd += " --keystone_auth_port %s" % ks_auth_port
        cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
        cmd += " --keystone_admin_user %s" % ks_admin_user
        cmd += " --keystone_admin_password %s" % ks_admin_password
        cmd += " --nova_password %s" % get_nova_password()
        cmd += " --neutron_password %s" % get_neutron_password()
        cmd += " --service_tenant_name %s" % get_keystone_service_tenant_name()
        cmd += " --region_name %s" % get_region_name()
        if cpu_mode is not None:
            cmd += " --cpu_mode %s" % cpu_mode
            if cpu_mode == 'custom':
                if cpu_model is None:
                    raise Exception('cpu model is required for custom cpu mode')
                cmd += " --cpu_model %s" % cpu_model

    # Add metadata_secret if available
    if metadata_secret:
        cmd += " --metadata_secret %s" % metadata_secret

    # HA arguments
    internal_vip = get_openstack_internal_vip()
    if internal_vip:
        # Highly availbale setup
        cmd += " --internal_vip %s" % internal_vip
    external_vip = get_from_testbed_dict('ha', 'external_vip', None)
    if external_vip:
        cmd += ' --external_vip %s' % external_vip
    if manage_nova_compute == 'no':
        cmd = cmd + "  --no_contrail_openstack"
    contrail_internal_vip = get_contrail_internal_vip()
    if contrail_internal_vip:
        # Highly availbale setup with mulitple interfaces
        cmd += " --contrail_internal_vip %s" % contrail_internal_vip
    if internal_vip or contrail_internal_vip:
        cmd += " --mgmt_self_ip %s" % compute_mgmt_ip

    if configure_nova == 'no':
        cmd = cmd + "  --no_nova_config"

    # Simple Gateway(vgw) arguments
    (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list) = get_vgw_details(host_string)
    if set_vgw:
        cmd += " --vgw_public_subnet %s" % str([(';'.join(str(e) for e in public_subnet)).replace(" ","")])
        cmd += " --vgw_public_vn_name %s" % str([(';'.join(str(e) for e in public_vn_name)).replace(" ","")])
        cmd += " --vgw_intf_list %s" % str([(';'.join(str(e) for e in vgw_intf_list)).replace(" ","")])
        if gateway_routes:
            cmd += " --vgw_gateway_routes %s" % str([(';'.join(str(e) for e in gateway_routes)).replace(" ","")])

    # Qos Arguments
    (set_qos, qos_logical_queue, qos_queue_id, default_hw_queue) = get_qos_details(host_string)
    if set_qos:
        cmd += " --qos_logical_queue %s" % ' '.join(qos_logical_queue)
        cmd += " --qos_queue_id %s" %  ' '.join(qos_queue_id)
        if default_hw_queue:
            cmd += " --default_hw_queue"

    # Qos priority group arguments
    (set_priority, priority_id, priority_bandwidth, priority_scheduling) = get_priority_group_details(host_string)
    set_priority = False
    if set_priority:
        cmd += " --priority_id %s" % ' '.join(priority_id)
        cmd += " --priority_scheduling %s" % ' '.join(priority_scheduling)
        cmd += " --priority_bandwidth %s" % ' '.join(priority_bandwidth)

    compute_as_gateway_list = get_compute_as_gateway_list()
    if compute_as_gateway_list:
        cmd += " --gateway_server_list %s" % ' '.join(compute_as_gateway_list)

    sriov_string = get_sriov_details(host_string)
    if sriov_string:
        cmd += " --sriov %s" % sriov_string
        
    if 'vcenter_compute' in env.roledefs:
        compute_host = 'root' + '@' + compute_mgmt_ip
        if compute_host in env.roledefs['vcenter_compute'][:]:
            vcenter_info = getattr(env, 'vcenter_servers', None)
            for v in vcenter_info.keys():
                 vcenter_server = vcenter_info[v]
                 datacenters = get_vcenter_datacenters(vcenter_server)
                 for dc in datacenters: 
                     dc_info = vcenter_server['datacenters'][dc]
                     vcenter_compute_nodes = get_vcenter_compute_nodes(dc_info)
                     if compute_mgmt_ip in vcenter_compute_nodes:
                         vcenter_compute_node = compute_mgmt_ip
                         cmd += " --vcenter_server %s" % vcenter_server['server']
                         cmd += " --vcenter_username %s" % vcenter_server['username']
                         cmd += " --vcenter_password %s" % vcenter_server['password']

                         for dvs in dc_info['dv_switches'].keys():
                              dvs_info = dc_info['dv_switches'][dvs]
                              if vcenter_compute_node == dvs_info['vcenter_compute']:
                                  dv_switch = dvs
                                  cluster_list = dvs_info['clusters']
                                  break

                         cluster_list_now = ""
                         for cluster in cluster_list:
                              cluster_list_now += cluster
                              cluster_list_now += ","
                         cluster_list_now = cluster_list_now.rstrip(',')
                         cmd += " --vcenter_cluster %s" % cluster_list_now
                         cmd += " --vcenter_dvswitch %s" % dv_switch

    # Contrail with vmware as orchestrator
    esxi_data = get_vmware_details(host_string)
    if esxi_data:
        apply_esxi_defaults(esxi_data)
        datacenter_mtu = get_vcenter_datacenter_mtu(esxi_data['vcenter_server'])
        cmd += " --vmware %s" % esxi_data['ip']
        cmd += " --vmware_username %s" % esxi_data['username']
        cmd += " --vmware_passwd %s" % esxi_data['password']
        cmd += " --vmware_vmpg_vswitch %s" % esxi_data['vm_vswitch']
        mode = get_mode(env.host_string)
        cmd += " --mode %s" % mode
        cmd += " --vmware_vmpg_vswitch_mtu %s" % datacenter_mtu
        cmd += " --vmware_datanic_mtu %s" % datacenter_mtu

    dpdk = getattr(env, 'dpdk', None)
    if dpdk:
        if host_string in dpdk:
            cmd += " --dpdk"

    return cmd

def frame_vnc_collector_cmd(host_string, cmd='setup-vnc-collector'):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    collector_host_password = get_env_passwords(host_string)
    collector_host = get_control_host_string(host_string)
    ncollectors = len(env.roledefs['collector'])
    redis_master_host = get_control_host_string(env.roledefs['collector'][0])
    collector_ip_list = [hstr_to_ip(get_control_host_string(entry)) \
                          for entry in env.roledefs['collector']]

    if collector_host == redis_master_host:
        is_redis_master = True
    else:
        is_redis_master = False
    tgt_ip = hstr_to_ip(collector_host)
    database_host_list = [get_control_host_string(database_host) for database_host in env.roledefs['database']]
    if collector_host in database_host_list:
        database_host_list.remove(collector_host)
        database_host_list.insert(0, collector_host)
    cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in database_host_list]
    zookeeper_ip_list = [hstr_to_ip(get_control_host_string(config_host))
            for config_host in env.roledefs['cfgm']]
    redis_master_ip = hstr_to_ip(redis_master_host)
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    # Frame the command line to provision collector
    cmd += " --cassandra_ip_list %s" % (' '.join(cassandra_ip_list))
    cmd += " --zookeeper_ip_list %s" % (' '.join(zookeeper_ip_list))
    cmd += " --collector_ip_list %s" % (' '.join(collector_ip_list))
    cmd += " --amqp_ip_list %s" % ' '.join(get_amqp_servers())
    cmd += " --amqp_port %s" % get_amqp_port()
    amqp_password = get_amqp_password()
    if amqp_password:
        cmd += " --amqp_password %s" % amqp_password
    cmd += " --cfgm_ip %s" % cfgm_ip
    if apiserver_ssl_enabled():
        cmd += " --apiserver_insecure %s" % get_apiserver_insecure_flag()
        cmd += " --apiserver_certfile %s" % get_apiserver_certfile()
        cmd += " --apiserver_keyfile %s" % get_apiserver_keyfile()
        cmd += " --apiserver_cafile %s" % get_apiserver_cafile()
    cmd += " --self_collector_ip %s" % tgt_ip
    cmd += " --num_nodes %d " % ncollectors
    analytics_syslog_port = get_collector_syslog_port()
    if analytics_syslog_port is not None:
        cmd += "--analytics_syslog_port %d " % analytics_syslog_port
    analytics_database_ttl = get_database_ttl()
    if analytics_database_ttl is not None:
        cmd += "--analytics_data_ttl %d " % analytics_database_ttl
    analytics_config_audit_ttl = get_analytics_config_audit_ttl()
    if analytics_config_audit_ttl is not None:
        cmd += "--analytics_config_audit_ttl %d " % analytics_config_audit_ttl
    analytics_statistics_ttl = get_analytics_statistics_ttl()
    if analytics_statistics_ttl is not None:
        cmd += "--analytics_statistics_ttl %d " % analytics_statistics_ttl
    analytics_flow_ttl = get_analytics_flow_ttl()
    if analytics_flow_ttl is not None:
        cmd += "--analytics_flow_ttl %d " % analytics_flow_ttl
    analytics_redis_password = get_redis_password()
    if analytics_redis_password is not None:
        cmd += "--redis_password %s " % analytics_redis_password
    cmd += "--kafka_enabled %s" % get_kafka_enabled()
    orchestrator = get_orchestrator()
    if orchestrator == 'openstack':
        # Pass keystone arguments in case for openstack orchestrator
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % get_authserver_ip()
        cmd += " --keystone_version %s" % get_keystone_version()
        cmd += " --keystone_admin_user %s" % ks_admin_user
        cmd += " --keystone_admin_passwd %s" % ks_admin_password
        cmd += " --keystone_admin_tenant_name %s" % \
                get_admin_tenant_name()
        cmd += " --keystone_auth_protocol %s" % \
                get_authserver_protocol()
        cmd += " --keystone_auth_port %s" % get_authserver_port()
        cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
        if keystone_ssl_enabled():
            cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
            cmd += " --keystone_certfile %s" % get_keystone_certfile()
            cmd += " --keystone_keyfile %s" % get_keystone_keyfile()
            cmd += " --keystone_cafile %s" % get_keystone_cafile()

    internal_vip = get_contrail_internal_vip()
    if internal_vip:
        # Highly Available setup
        cmd += " --internal_vip %s" % internal_vip
    if cassandra_user is not None:
        cmd += " --cassandra_user %s" % cassandra_user
        cmd += " --cassandra_password %s" % cassandra_password

    analytics_aaa_mode = get_analytics_aaa_mode()
    if orchestrator != 'openstack':
        analytics_aaa_mode = 'no-auth'
    cmd += " --aaa_mode %s" % analytics_aaa_mode
    cloud_admin_role = get_cloud_admin_role()
    if cloud_admin_role:
        cmd += " --cloud_admin_role %s" % cloud_admin_role
    return cmd


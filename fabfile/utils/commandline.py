from fabric.api import env, sudo

from host import *
from cluster import *
from analytics import *
from interface import *
from multitenancy import *
from fabfile.tasks.esxi_defaults import apply_esxi_defaults

def frame_vnc_database_cmd(host_string, cmd="setup-vnc-database"):
    database_host = host_string
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    database_host_list = [get_control_host_string(entry)\
                          for entry in env.roledefs['database']]
    database_ip_list = [hstr_to_ip(db_host) for db_host in database_host_list]
    database_host=get_control_host_string(host_string)
    database_host_password=get_env_passwords(host_string)
    tgt_ip = hstr_to_ip(database_host)
    #derive kafka broker id from the list of servers specified
    broker_id = sorted(database_ip_list).index(tgt_ip)
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    cmd += " --self_ip %s" % tgt_ip
    cmd += " --cfgm_ip %s" % cfgm_ip
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
    cmd += " --zookeeper_ip_list %s" % ' '.join(database_ip_list)
    cmd += " --database_index %d" % (database_host_list.index(database_host) + 1)
    minimum_diskGB = get_minimum_diskGB()
    if minimum_diskGB is not None:
        cmd += " --minimum_diskGB %s" % minimum_diskGB
    cmd += " --kafka_broker_id %d" % broker_id
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
                                  openstack_node=env.host_string)
    (_, openstack_admin_password) = get_authserver_credentials()
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = hstr_to_ip(cfgm_host)
    internal_vip = get_openstack_internal_vip()

    cmd += " --self_ip %s" % self_ip
    cmd += " --keystone_ip %s" % authserver_ip
    cmd += " --keystone_admin_passwd %s" % openstack_admin_password
    cmd += " --cfgm_ip %s " % cfgm_ip
    cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
    cmd += " --amqp_server_ip %s" % amqp_server_ip
    cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
    cmd += " --service_token %s" % get_service_token()
    cmd += ' --openstack_index %s' % (env.roledefs['openstack'].index(
                                          host_string) + 1)
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
    if cfgm_host in collector_host_list:
        collector_ip = tgt_ip
    else:
        # Select based on index
        hindex = cfgm_host_list.index(cfgm_host)
        hindex = hindex % len(env.roledefs['collector'])
        collector_host = get_control_host_string(
                             env.roledefs['collector'][hindex])
        collector_ip = hstr_to_ip(collector_host)
    mt_opt = '--multi_tenancy' if get_mt_enable() else ''
    cassandra_ip_list = [hstr_to_ip(get_control_host_string(cassandra_host))\
                         for cassandra_host in env.roledefs['database']]
    amqp_server_ip = get_contrail_amqp_server()
    orch = get_orchestrator()
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    cmd += " --self_ip %s" % tgt_ip
    cmd += " --collector_ip %s %s" % (collector_ip, mt_opt)
    cmd += " --cassandra_ip_list %s" % ' '.join(cassandra_ip_list)
    cmd += " --zookeeper_ip_list %s" % ' '.join(cassandra_ip_list)
    cmd += " --quantum_port %s" % quantum_port
    cmd += " --nworkers %d" % nworkers
    cmd += " --service_token %s" % get_service_token()
    cmd += " --amqp_server_ip %s" % amqp_server_ip
    cmd += " --orchestrator %s" % orch
    haproxy = get_haproxy()
    if haproxy:
        cmd += " --haproxy %s" % haproxy
    if orch == 'openstack':
        (_, openstack_admin_password) = get_authserver_credentials()
        authserver_ip = get_authserver_ip()
        # Pass keystone arguments in case for openstack orchestrator
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --keystone_admin_passwd %s" % openstack_admin_password
        cmd += " --keystone_service_tenant_name %s" % get_keystone_service_tenant_name()
        cmd += ' --neutron_password %s' % get_neutron_password()
        cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
        cmd += " --keystone_auth_port %s" % get_authserver_port()
        cmd += " --keystone_admin_token %s" % get_keystone_admin_token()
        cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
        cmd += " --region_name %s" % get_region_name()
        manage_neutron = get_manage_neutron()
        if manage_neutron == 'no':
            # Skip creating neutron service tenant/user/role etc in keystone.
            cmd += ' --manage_neutron %s' % manage_neutron
    else:
        cmd += ' --manage_neutron no'
    internal_vip = get_contrail_internal_vip()
    if internal_vip:
        # Highly available setup
        cmd += ' --internal_vip %s' % (internal_vip)
    if cassandra_user is not None:
        cmd += ' --cassandra_user %s' % (cassandra_user)
        cmd += ' --cassandra_password %s' % (cassandra_password)
    return cmd

def frame_vnc_webui_cmd(host_string, cmd="setup-vnc-webui"):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = hstr_to_ip(cfgm_host)
    webui_host = get_control_host_string(host_string)
    ncollectors = len(env.roledefs['collector'])
    database_host_list=[]
    for entry in env.roledefs['database']:
        database_host_list.append(get_control_host_string(entry))
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
    cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in database_host_list]
    orch = get_orchestrator()

    # If redis password is specified in testbed file, then add that to the
    # redis config file
    redis_password = get_redis_password()

    cmd += " --cfgm_ip %s" % cfgm_ip
    cmd += " --collector_ip %s" % collector_ip
    cmd += " --cassandra_ip_list %s" % ' '.join(cassandra_ip_list)
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
        openstack_host = get_control_host_string(env.roledefs['openstack'][0])
        openstack_ip = hstr_to_ip(openstack_host)
        authserver_ip = get_authserver_ip()
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --openstack_ip %s" % openstack_ip
        cmd += " --admin_user %s" % ks_admin_user
        cmd += " --admin_password %s" % ks_admin_password
        cmd += " --admin_token %s" % get_keystone_admin_token()
        cmd += " --admin_tenant_name %s" % get_admin_tenant_name()
    elif orch == 'vcenter':
        vcenter_info = getattr(env, 'vcenter', None)
        if not vcenter_info:
            print 'Error: vcenter block is not defined in testbed file.Exiting'
            return
        # vcenter provisioning parameters
        cmd += " --vcenter_ip %s" % vcenter_info['server']
        cmd += " --vcenter_port %s" % vcenter_info['port']
        cmd += " --vcenter_auth %s" % vcenter_info['auth']
        cmd += " --vcenter_datacenter %s" % vcenter_info['datacenter']
        cmd += " --vcenter_dvswitch %s" % vcenter_info['dv_switch']['dv_switch_name']

    return cmd

def frame_vnc_control_cmd(host_string, cmd='setup-vnc-control'):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    control_host = get_control_host_string(host_string)
    tgt_ip = hstr_to_ip(control_host)
    collector_host_list=[]
    for entry in env.roledefs['collector']:
        collector_host_list.append(get_control_host_string(entry))
    control_host_list=[]
    for entry in env.roledefs['control']:
        control_host_list.append(get_control_host_string(entry))
    # Prefer local collector node
    if control_host in collector_host_list:
        collector_ip = tgt_ip
    else:
        # Select based on index
        hindex = control_host_list.index(control_host)
        hindex = hindex % len(env.roledefs['collector'])
        collector_host = get_control_host_string(env.roledefs['collector'][hindex])
        collector_ip = hstr_to_ip(collector_host)
    cmd += ' --self_ip %s' % tgt_ip
    cmd += ' --cfgm_ip %s' % cfgm_ip
    cmd += ' --collector_ip %s' % collector_ip

    return cmd

def frame_vnc_compute_cmd(host_string, cmd='setup-vnc-compute',
                          manage_nova_compute='yes', configure_nova='yes'):
    orch = get_orchestrator()
    ncontrols = len(env.roledefs['control'])
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
    cmd += " --ncontrols %s" % ncontrols
    cmd += " --amqp_server_ip %s" % amqp_server_ip
    cmd += " --service_token %s" % get_service_token()
    cmd += " --orchestrator %s" % get_orchestrator()
    cmd += " --hypervisor %s" % get_hypervisor(host_string)
    haproxy = get_haproxy()
    if haproxy:
        cmd += " --haproxy %s" % haproxy

    if tgt_ip != compute_mgmt_ip:
        cmd += " --non_mgmt_ip %s" % tgt_ip
        cmd += " --non_mgmt_gw %s" % tgt_gw

    if orch == 'openstack':
        openstack_mgmt_ip = hstr_to_ip(env.roledefs['openstack'][0])
        authserver_ip = get_authserver_ip()
        ks_auth_protocol = get_authserver_protocol()
        ks_auth_port = get_authserver_port()
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % authserver_ip
        cmd += " --openstack_mgmt_ip %s" % openstack_mgmt_ip
        cmd += " --keystone_auth_protocol %s" % ks_auth_protocol
        cmd += " --keystone_auth_port %s" % ks_auth_port
        cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
        cmd += " --keystone_admin_user %s" % ks_admin_user
        cmd += " --keystone_admin_password %s" % ks_admin_password
        cmd += " --nova_password %s" % get_nova_password()
        cmd += " --neutron_password %s" % get_neutron_password()
        cmd += " --service_tenant_name %s" % get_keystone_service_tenant_name()
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

    if 'vcenter_compute' in env.roles:
        if compute_mgmt_ip in env.roledefs['vcenter_compute'][0]:
            vcenter_info = getattr(env, 'vcenter', None)
            cmd += " --vcenter_server %s" % vcenter_info['server']
            cmd += " --vcenter_username %s" % vcenter_info['username']
            cmd += " --vcenter_password %s" % vcenter_info['password']
            cluster_list = vcenter_info['cluster']
            cluster_list_now = "" 
            for cluster in cluster_list:
                cluster_list_now += cluster
                cluster_list_now += ","
            cluster_list_now = cluster_list_now.rstrip(',')
            cmd += " --vcenter_cluster %s" % cluster_list_now 
            cmd += " --vcenter_dvswitch %s" % vcenter_info['dv_switch']['dv_switch_name']    

    # Contrail with vmware as orchestrator
    esxi_data = get_vmware_details(host_string)
    if esxi_data:
        apply_esxi_defaults(esxi_data)
        cmd += " --vmware %s" % esxi_data['ip']
        cmd += " --vmware_username %s" % esxi_data['username']
        cmd += " --vmware_passwd %s" % esxi_data['password']
        cmd += " --vmware_vmpg_vswitch %s" % esxi_data['vm_vswitch']
        if orch is 'vcenter':
            # Setting mtu when vmware is orchestrator
            mtu = "1500"
            cmd += " --vmware_vmpg_vswitch_mtu %s" % mtu
        else:
            cmd += " --vmware_vmpg_vswitch_mtu %s" % esxi_data['vm_vswitch_mtu']
        cmd += " --mode %s" % esxi_data['contrail_vm']['mode']

    dpdk = getattr(env, 'dpdk', None)
    if dpdk:
        if env.host_string in dpdk:
            cmd += " --dpdk"

    return cmd

def frame_vnc_collector_cmd(host_string, cmd='setup-vnc-collector'):
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
    collector_host_password = get_env_passwords(host_string)
    collector_host = get_control_host_string(host_string)
    ncollectors = len(env.roledefs['collector'])
    redis_master_host = get_control_host_string(env.roledefs['collector'][0])
    if collector_host == redis_master_host:
        is_redis_master = True
    else:
        is_redis_master = False
    tgt_ip = hstr_to_ip(collector_host)
    cassandra_host_list = [get_control_host_string(cassandra_host) for cassandra_host in env.roledefs['database']]
    if collector_host in cassandra_host_list:
        cassandra_host_list.remove(collector_host)
        cassandra_host_list.insert(0, collector_host)
    cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in cassandra_host_list]
    redis_master_ip = hstr_to_ip(redis_master_host)
    cassandra_user = get_cassandra_user()
    cassandra_password = get_cassandra_password()

    # Frame the command line to provision collector
    cmd += " --cassandra_ip_list %s" % (' '.join(cassandra_ip_list))
    cmd += " --cfgm_ip %s" % cfgm_ip
    cmd += " --self_collector_ip %s" % tgt_ip
    cmd += " --num_nodes %d " % ncollectors
    analytics_syslog_port = get_collector_syslog_port()
    if analytics_syslog_port is not None:
        cmd += "--analytics_syslog_port %d " % analytics_syslog_port
    analytics_database_ttl = get_database_ttl()
    if analytics_database_ttl is not None:
        cmd += "--analytics_data_ttl %d " % analytics_database_ttl
    else:
        #if nothing is provided we default to 48h
        cmd += "--analytics_data_ttl 48 "
    analytics_config_audit_ttl = get_analytics_config_audit_ttl()
    if analytics_config_audit_ttl is not None:
        cmd += "--analytics_config_audit_ttl %d " % analytics_config_audit_ttl
    else:
        cmd += "--analytics_config_audit_ttl -1 "
    analytics_statistics_ttl = get_analytics_statistics_ttl()
    if analytics_statistics_ttl is not None:
        cmd += "--analytics_statistics_ttl %d " % analytics_statistics_ttl
    else:
        cmd += "--analytics_statistics_ttl -1 "
    analytics_flow_ttl = get_analytics_flow_ttl()
    if analytics_flow_ttl is not None:
        cmd += "--analytics_flow_ttl %d " % analytics_flow_ttl
    else:
        cmd += "--analytics_flow_ttl -1 "
    analytics_redis_password = get_redis_password()
    if analytics_redis_password is not None:
        cmd += "--redis_password %s " % analytics_redis_password
    cmd += "--kafka_enabled %s" % get_kafka_enabled()
    if get_orchestrator() == 'openstack':
        # Pass keystone arguments in case for openstack orchestrator
        ks_admin_user, ks_admin_password = get_authserver_credentials()
        cmd += " --keystone_ip %s" % get_authserver_ip()
        cmd += " --keystone_admin_user %s" % ks_admin_user
        cmd += " --keystone_admin_passwd %s" % ks_admin_password
        cmd += " --keystone_admin_tenant_name %s" % \
                get_keystone_service_tenant_name()
        cmd += " --keystone_auth_protocol %s" % \
                get_authserver_protocol()
        cmd += " --keystone_auth_port %s" % get_authserver_port()
        cmd += " --keystone_admin_token %s" % get_keystone_admin_token()
        cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()

    internal_vip = get_contrail_internal_vip()
    if internal_vip:
        # Highly Available setup
        cmd += " --internal_vip %s" % internal_vip
    if cassandra_user is not None:
        cmd += " --cassandra_user %s" % cassandra_user
        cmd += " --cassandra_password %s" % cassandra_password

    return cmd


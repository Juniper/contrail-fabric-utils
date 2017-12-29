from collections import OrderedDict
import os
from collections import Counter
from fabfile.config import *
from netaddr import IPAddress


def _disable_logging():
    output['running'] = False
    output['stdout'] = False
    output['stderr'] = False
    output['warnings'] = False
    try:
        file_name = sys.stdout.log.name
        sys.stdout.log.close()
        os.remove(file_name)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    except:
        pass


def _print_table(headers, rows, sort_data=False, title=None,
                 hide_headers=False, show_empty=False, space='  '):
    if len(rows) > 0:
        print('')
        length_dict = {}
        for header in headers:
            length_dict[header] = len(header) + 1

        for row in rows:
            row_dict = dict(zip(headers, row))
            for key, value in row_dict.items():
                lines = str(value).splitlines()
                if value:
                    max_len = max([len(line) for line in lines])
                else:
                    max_len = 0
                if max_len >= length_dict[key]:
                    length_dict[key] = max_len + 1

        if sort_data:
            rows.sort()

        header_format = ""
        separator = ""
        for i, key in enumerate(headers):
            header_format = header_format + "{" + str(i) + ":<" \
                            + str(length_dict[key]) + "}" + space
            separator = separator + "-" * length_dict[key] + space

        if title:
            print('-' * len(separator.strip()))
            title_format = "{0:^" + str(len(separator.strip())) + "}"
            print(title_format.format(title))
            print('-' * len(separator.strip()))

        if not hide_headers:
            print(header_format.format(*headers))
            print(separator)
        for row in rows:
            print(header_format.format(*row))
    else:
        if show_empty:
            if title:
                print('')
                print('-' * (len(title) + 4))
                print('  ' + title + '  ')
                print('-' * (len(title) + 4))


def _print_dict(dictionary, title=None):
    if len(dictionary) > 0:
        print('')
        key_max_len = max([len(key) for key in dictionary.keys()])
        values = []
        for value in dictionary.values():
            if type(value) is list:
                values.extend([child_value for child_value in value])
            elif value:
                values.append(value)
        value_max_len = max([len(str(value)) for value in values])
        line_format = '{0:' + str(key_max_len) + '} : {1}'
        second_format = '{0:' + str(key_max_len) + '}   {1}'
        if title:
            title_len = max(len(title) + 4, key_max_len + value_max_len + 3)
            print("-" * title_len)
            title_format = "{0:^" + str(title_len) + "}"
            print(title_format.format(title))
            print("-" * title_len)

        for key, value in dictionary.items():
            if type(value) is list:
                if len(value) == 0:
                    print(line_format.format(key, '-'))
                else:
                    for i, child_value in enumerate(value):
                        if i == 0:
                            print(line_format.format(key, child_value))
                        else:
                            print(second_format.format('', child_value))
            else:
                print(line_format.format(key, value))


def _print_env_dict(env_dict, defaults, title=None):
    results = OrderedDict()
    for k, v in defaults.items():
        if env_dict.get(k):
            if v == '*mask*':
                results[k] = '******'
            else:
                results[k] = env_dict[k]
        elif k.startswith('env.') and getattr(env, k.split('.')[-1], None):
            if v == '*mask*':
                results[k] = '******'
            else:
                results[k] = getattr(env, k.split('.')[-1])
        elif getattr(testbed, k, None):
            if v == '*mask*':
                results[k] = '******'
            else:
                results[k] = getattr(testbed, k)
        elif v not in [None, '*mask*']:
            if v == 'default':
                results[k] = 'default'
            else:
                results[k] = 'default ({})'.format(v)
        else:
            results[k] = '-'
    _print_dict(results, title=title)


def _print_message(msgs):
    msgs = [m for m in msgs if m]
    if len(msgs) > 0:
        print('')
        max_len = max([len(msg) for msg in msgs] + [9])
        print('Messages')
        print('-' * max_len)
        for msg in msgs:
            print(msg)


def _update_progress(host_string, host_strings):
    current = host_strings.index(host_string)
    max_len = len(host_strings)
    sys.stdout.write('\r')
    percent = (current + 1) * 100 / max_len
    bar = '[{:20}]'.format('=' * (percent / 5))
    sys.stdout.write('{} {}% ({}/{})'.format(bar, percent, current + 1, max_len))
    sys.stdout.flush()
    if host_string == host_strings[-1]:
        print('')


def _hstr_to_ip(host_string):
    return host_string.split('@')[-1]


def _hstr_to_name(host_string):
    if 'all' in env.hostnames.keys():
        name_dict = OrderedDict(zip(env.roledefs['all'], env.hostnames['all']))
    else:
        name_dict = env.hostnames
    return name_dict.get(host_string, host_string.split('@')[-1])


def _hstr_to_user(host_string):
    if len(host_string.split('@')) == 2:
        user = host_string.split('@')[0]
    else:
        user = None
    return user


def _hstr_to_ctrl(host_string, with_length=False):
    ctrl_ip = None
    control_data = getattr(testbed, 'control_data', {})
    if host_string in control_data:
        if with_length:
            ctrl_ip = control_data[host_string]['ip']
        else:
            ctrl_ip = control_data[host_string]['ip'].split('/')[0]
    return ctrl_ip


def _hstr_to_dev(host_string):
    control_data = getattr(testbed, 'control_data', {})
    with settings(host_string=host_string, warn_only=True):
        if sudo('ip link show dev vhost0').succeeded:
            device = 'vhost0'
        elif host_string in control_data:
            host_ctrl_data = control_data[host_string]
            if host_ctrl_data.get('vlan'):
                device = '{}.{}'.format(host_ctrl_data['device'], host_ctrl_data['vlan'])
            else:
                device = host_ctrl_data['device']
        else:
            mgmt_ip = _hstr_to_ip(host_string)
            cmd = "ip route show | grep 'src {}\s*'$ | awk '{{print $3}}'".format(mgmt_ip)
            device = sudo(cmd)
    return device


def _ping_hstr(src_hstr, dst_hstr, use_ctrl=False, count=3, interval=0.3, deadline=1):
    src_name = _hstr_to_name(src_hstr)
    dst_name = _hstr_to_name(dst_hstr)
    dst_ip = _hstr_to_ip(dst_hstr)
    with settings(host_string=src_hstr, warn_only=True):
        if use_ctrl:
            device = _hstr_to_dev(src_hstr)
            result = sudo('ping -c {} -i {} -w {} -I {} {}'.format(count, interval, deadline, device, dst_ip))
        else:
            result = sudo('ping -c {} -i {} -w {} {}'.format(count, interval, deadline, dst_ip))
    if result.failed:
        return 'NG', 'ERROR: {} is not reachable from {}.'.format(dst_name, src_name)
    else:
        return 'OK', None


def _get_node_roles(host_string):
    node_roles = []
    for role in sorted(env.roledefs.keys()):
        if host_string in env.roledefs[role]:
            node_roles.append(role)
    return node_roles


def _get_role_members(include_roles, exclude_roles=None):
    include_hosts = []
    exclude_hosts = []
    for include_role in include_roles:
        include_hosts += [host for host in env.roledefs.get(include_role, []) if host not in include_hosts]
    if exclude_roles:
        for exclude_role in exclude_roles:
            exclude_hosts += [host for host in env.roledefs.get(exclude_role, []) if host not in exclude_hosts]
    members = [host for host in include_hosts if host not in exclude_hosts]
    return members


@task
def show_testbed():
    """
    Print testbed parameters in an easy-to-read format.
    USAGE: fab show_testbed
    """
    _disable_logging()
    output['stderr'] = True

    host_strings = []
    for role, members in env.roledefs.items():
        for member in members:
            if member not in host_strings:
                host_strings.append(member)

    host_headers = ['Hostname', 'User', 'Password', 'OS Type', 'Control IP', 'Management IP', 'Roles']
    host_rows = []
    env_ostypes = getattr(env, 'ostypes', {})
    for host_string in host_strings:
        host_name = _hstr_to_name(host_string)
        user = _hstr_to_user(host_string)
        if host_string in env.passwords:
            password = '******'
        else:
            password = '-'
        os_type = env_ostypes.get(host_string, '-')
        mgmt_ip = _hstr_to_ip(host_string)
        control_data = getattr(testbed, 'control_data', None)
        if control_data and host_string in control_data:
            control_ip = control_data[host_string]['ip'].split('/')[0]
        else:
            control_ip = '-'
        node_roles = ' '.join(_get_node_roles(host_string))
        host_rows.append([host_name, user, password, os_type, control_ip, mgmt_ip, node_roles])
    _print_table(host_headers, host_rows, title='Host Properties')

    env_control_data = getattr(testbed, 'control_data', None)
    if env_control_data:
        cd_headers = ['Hostname', 'IP Address', 'Gateway', 'Device', 'VLAN ID']
        cd_rows = []
        for host_string, ifcfg in env_control_data.items():
            host_name = _hstr_to_name(host_string)
            ip = ifcfg.get('ip')
            gw = ifcfg.get('gw')
            dev = ifcfg.get('device')
            vlan = ifcfg.get('vlan', '-')
            cd_rows.append([host_name, ip, gw, dev, vlan])
        _print_table(cd_headers, cd_rows, title='Control-Data Network (control_data)')

    env_static_route = getattr(testbed, 'static_route', None)
    if env_static_route:
        static_headers = ['Hostname', 'Destination', 'Netmask', 'Gateway', 'Interface']
        static_rows = []
        for host_string, routes in env_static_route.items():
            host_name = _hstr_to_name(host_string)
            for route in routes:
                ip = route.get('ip')
                netmask = route.get('netmask')
                gw = route.get('gw')
                intf = route.get('intf')
                static_rows.append([host_name, ip, netmask, gw, intf])
        _print_table(static_headers, static_rows, title='Static Routes (static_route)')

    env_vrouter_module_params = getattr(env, 'vrouter_module_params', None)
    if env_vrouter_module_params:
        vrouter_param_headers = ['Hostname', 'flow_entries', 'mpls_labels', 'nexthops', 'vrfs', 'macs']
        vrouter_param_rows = []
        for host_string, params in env_vrouter_module_params.items():
            host_name = _hstr_to_name(host_string)
            flow_entries = route.get('flow_entries', 'default')
            mpls_labels = route.get('mpls_labels', 'default')
            nexthops = route.get('nexthops', 'default')
            vrfs = route.get('vrfs', 'default')
            macs = route.get('macs', 'default')
            vrouter_param_rows.append([host_name, flow_entries, mpls_labels, nexthops, vrfs, macs])
        _print_table(vrouter_param_headers, vrouter_param_rows,
                     title='vRouter Module Parameters (env.vrouter_module_params)')

    ca_cert_dict = {'ca_cert_file': getattr(env, 'ca_cert_file', '-')}
    _print_dict(ca_cert_dict, title='CA Certificate File for ToR Agent')

    env_tor_agent = getattr(env, 'tor_agent', None)
    if env_tor_agent:
        tsn_rows = []
        tsn_headers = ['ToR Agent ID', 'TSN Name', 'TSN IP', 'ToR Agent Name',
                       'ToR Agent HTTP Port']
        tor_rows = []
        tor_headers = ['ToR Agent ID', 'TSN Name', 'ToR IP', 'ToR Name', 'ToR Tunnel IP',
                       'Vendor Name', 'Product Name']
        ovs_rows = []
        ovs_headers = ['ToR Agent ID', 'TSN Name', 'ToR Type', 'Protocol', 'Port', 'Keepalive Timer']
        for host_string in env_tor_agent.keys():
            for tor_agent in env_tor_agent[host_string]:
                tor_id = tor_agent.get('tor_id', '-')
                tor_agent_id = tor_agent.get('tor_agent_id', tor_id)
                if tor_agent_id != '-':
                    tor_agent_id = int(tor_agent_id)
                tor_tsn_ip = tor_agent.get('tor_tsn_ip', '-')
                tor_tsn_name = tor_agent.get('tor_tsn_name', '-')
                tor_agent_name = 'default ({}-{})'.format(tor_tsn_name, tor_agent_id)
                tor_agent_name = tor_agent.get('tor_agent_name', tor_agent_name)
                tor_http_server_port = tor_agent.get('tor_http_server_port', '-')
                tor_agent_http_server_port = tor_agent.get('tor_agent_http_server_port', tor_http_server_port)
                tsn_rows.append([tor_agent_id, tor_tsn_name, tor_tsn_ip, tor_agent_name,
                                 tor_agent_http_server_port])

                tor_ip = tor_agent.get('tor_ip', '-')
                tor_name = tor_agent.get('tor_name', '-')
                tor_tunnel_ip = tor_agent.get('tor_tunnel_ip', '-')
                tor_vendor_name = tor_agent.get('tor_vendor_name', '-')
                tor_product_name = tor_agent.get('tor_product_name', '-')
                tor_rows.append([tor_agent_id, tor_tsn_name, tor_ip, tor_name, tor_tunnel_ip,
                                 tor_vendor_name, tor_product_name])

                tor_type = tor_agent.get('tor_type', '-')
                tor_ovs_protocol = tor_agent.get('tor_ovs_protocol', '-')
                tor_ovs_port = tor_agent.get('tor_ovs_port', '-')

                tor_agent_ovs_ka = tor_agent.get('tor_agent_ovs_ka', '-')
                ovs_rows.append([tor_agent_id, tor_tsn_name, tor_type, tor_ovs_protocol, tor_ovs_port,
                                 tor_agent_ovs_ka])

        _print_table(tsn_headers, sorted(tsn_rows), title='ToR Agent')
        _print_table(tor_headers, sorted(tor_rows), title='ToR Switch')
        _print_table(ovs_headers, sorted(ovs_rows), title='OVSDB Connection')

    env_openstack = getattr(env, 'openstack', {})
    os_defaults = OrderedDict()
    os_defaults['service_token'] = '*mask*'
    os_defaults['amqp_host'] = None
    os_defaults['manage_amqp'] = 'no'
    os_defaults['osapi_compute_workers'] = 40
    os_defaults['conductor_workers'] = 40
    _print_env_dict(env_openstack, os_defaults, title='OpenStack (env.openstack)')

    os_misc_defaults = OrderedDict()
    os_misc_defaults['env.openstack_admin_password'] = '*mask*'
    os_misc_defaults['neutron_metadata_proxy_shared_secret'] = '*mask*'
    _print_env_dict({}, os_misc_defaults, title='OpenStack')

    env_keystone = getattr(env, 'keystone', {})
    keystone_defaults = OrderedDict()
    keystone_defaults['keystone_ip'] = None
    keystone_defaults['auth_url'] = None
    keystone_defaults['auth_protocol'] = 'http'
    keystone_defaults['auth_port'] = '35357'
    keystone_defaults['endpoint_type'] = None
    keystone_defaults['project_domain_name'] = None
    keystone_defaults['admin_token'] = '*mask*'
    keystone_defaults['admin_user'] = 'admin'
    keystone_defaults['admin_password'] = '*mask*'
    keystone_defaults['service_tenant'] = '*mask*'
    keystone_defaults['admin_tenant'] = 'admin'
    keystone_defaults['region_name'] = 'RegionOne'
    keystone_defaults['insecure'] = False
    keystone_defaults['certfile'] = '/etc/keystone/ssl/certs/keystone.pem'
    keystone_defaults['keyfile'] = '/etc/keystone/ssl/private/keystone_key.pem'
    keystone_defaults['cafile'] = '/etc/keystone/ssl/certs/keystone_ca.pem'
    keystone_defaults['manage_neutron'] = 'yes'
    keystone_defaults['keystone_sync_on_demand'] = True
    _print_env_dict(env_keystone, keystone_defaults, title='Keystone (env.keystone)')

    env_ha = getattr(env, 'ha', {})
    ha_defaults = OrderedDict()
    ha_defaults['internal_vip'] = None
    ha_defaults['external_vip'] = None
    ha_defaults['internal_virtual_router_id'] = 100
    ha_defaults['external_virtual_router_id'] = 100
    ha_defaults['contrail_internal_vip'] = None
    ha_defaults['contrail_external_vip'] = None
    ha_defaults['contrail_internal_virtual_router_id'] = 100
    ha_defaults['contrail_external_virtual_router_id'] = 100
    if env_ha.get('collector_external_vip'):
        ha_defaults['collector_external_vip'] = None
    if env_ha.get('collector_internal_vip'):
        ha_defaults['collector_internal_vip'] = None
    if env_ha.get('collector_external_virtual_router_id'):
        ha_defaults['collector_external_virtual_router_id'] = None
    if env_ha.get('collector_internal_virtual_router_id'):
        ha_defaults['collector_internal_virtual_router_id'] = None
    if env_ha.get('v1_contrail_internal_vip'):
        ha_defaults['v1_contrail_internal_vip'] = None
    if env_ha.get('v1_contrail_external_vip'):
        ha_defaults['v1_contrail_external_vip'] = None
    if env_ha.get('v1_contrail_internal_virtual_router_id'):
        ha_defaults['v1_contrail_internal_virtual_router_id'] = 100
    if env_ha.get('v1_contrail_external_virtual_router_id'):
        ha_defaults['v1_contrail_external_virtual_router_id'] = 100
    ha_defaults['haproxy_token'] = 'default'
    ha_defaults['nfs_server'] = env.roledefs.get('compute', ['-'])[0]
    ha_defaults['nfs_glance_path'] = '/var/tmp/glance-images/'
    _print_env_dict(env_ha, ha_defaults, title='High Availability (env.ha)')

    analytics_defaults = OrderedDict()
    analytics_defaults['database_dir'] = 'default'
    analytics_defaults['analytics_data_dir'] = None
    analytics_defaults['ssd_data_dir'] = None
    analytics_defaults['redis_password'] = None
    analytics_defaults['database_ttl'] = 48
    analytics_defaults['analytics_config_audit_ttl'] = 2160
    analytics_defaults['analytics_statistics_ttl'] = 168
    analytics_defaults['analytics_flow_ttl'] = 2
    analytics_defaults['minimum_diskGB'] = 256
    _print_env_dict({}, analytics_defaults, title='Analytics')

    mt_defaults = OrderedDict()
    mt_defaults['multi_tenancy'] = 'default'
    mt_defaults['aaa_mode'] = 'cloud-admin'
    mt_defaults['analytics_aaa_mode'] = 'cloud-admin'
    mt_defaults['cloud_admin_role'] = 'admin'
    _print_env_dict({}, mt_defaults, title='Multi-Tenancy')

    backup_defaults = OrderedDict()
    backup_defaults['backup_node'] = None
    backup_defaults['backup_db_path'] = '~/contrail_bkup_data/'
    backup_defaults['cassandra_backup'] = 'full'
    backup_defaults['skip_keyspace'] = None
    backup_defaults['service_token'] = '*mask*'
    _print_env_dict({}, backup_defaults, title='Backup')

    router_defaults = OrderedDict()
    router_defaults['router_asn'] = 64512
    router_defaults['ext_routers'] = None
    router_defaults['env.encap_priority'] = "'MPLSoUDP','MPLSoGRE','VXLAN'"
    _print_env_dict({}, router_defaults, title='Router')

    misc_defaults = OrderedDict()
    misc_defaults['env.ntp_server'] = None
    misc_defaults['env.interface_rename'] = False
    misc_defaults['do_parallel'] = False
    _print_env_dict({}, misc_defaults, title='Miscellaneous Properties')


@task
def verify_testbed(conn_check='yes'):
    """
    Verify testbed parameters.
    USAGE: fab verify_testbed[:conn_check=no]
    """
    _disable_logging()

    target_roles = ['cfgm', 'control', 'collector', 'database', 'webui', 'compute', 'tsn', 'toragent']
    host_strings = _get_role_members(target_roles)

    print('\n{:=^80}'.format(' Check variables '))

    # Add necessary variables for your environment.
    required_vars = ['env.roledefs', 'env.hostnames', 'env.passwords', 'env.ostypes']
    # required_vars = ['env.roledefs', 'env.hostnames']

    var_msgs = []
    var_rows = []
    var_headers = ['Variable Name', 'Exist']
    for var in required_vars:
        var_check = 'NO'
        if var.split('.')[0] == 'env':
            if getattr(env, var.split('.')[-1], None):
                var_check = 'YES'
            else:
                var_msgs.append('ERROR: {} does not exist.'.format(var))
        else:
            if getattr(testbed, var, None):
                var_check = 'YES'
            else:
                var_msgs.append('ERROR: {} does not exist.'.format(var))
        var_rows.append([var, var_check])
    _print_table(var_headers, var_rows, title='Variable Check')

    if 'all' in env.hostnames.keys():
        if len(env.roledefs['all']) != len(env.hostnames['all']):
            var_msgs.append("ERROR: Length of 'all' in env.roledefs and env.hostnames are not equal.")
        env_hostnames = dict(zip(env.roledefs['all'], env.hostnames['all']))
    else:
        env_hostnames = env.hostnames

    env_key_filename = getattr(env, 'key_filename', None)
    env_passwords = getattr(env, 'passwords', {})
    env_ostypes = getattr(env, 'ostypes', {})
    control_data = getattr(testbed, 'control_data', {})
    static_route = getattr(testbed, 'static_route', {})
    env_tor_agent = getattr(env, 'tor_agent', {})
    env_ha = getattr(env, 'ha', {})

    _print_message(var_msgs)

    print('\n{:=^80}'.format(' Check role assignment '))

    # Add necessary roles for your environment.
    required_roles = ['all', 'cfgm', 'control', 'collector', 'database', 'webui', 'build']
    required_roles += ['openstack', 'compute']
    required_roles += ['tsn', 'toragent']
    # required_roles += ['storage-master', 'storage-compute']
    # required_roles += ['oldcfgm', 'oldcontrol', 'oldcollector', 'olddatabase', 'oldwebui', 'oldbuild']

    role_msgs = []
    for role in required_roles:
        if role not in env.roledefs:
            role_msgs.append('ERROR: {} is not defined in env.roledefs.'.format(role))

    role_rows = []
    role_headers = ['Hostname', 'Roles']
    for host_string in host_strings:
        host_name = _hstr_to_name(host_string)
        assigned_roles = [role for role in env.roledefs.keys() if host_string in env.roledefs[role]]
        role_rows.append([host_name, assigned_roles])
    _print_table(role_headers, role_rows, title='Role Assignment Check')

    for host_string in env_tor_agent.keys():
        host_name = _hstr_to_name(host_string)
        for role in ['compute', 'tsn', 'toragent']:
            if host_string not in env.roledefs.get(role, []):
                role_msgs.append('ERROR: {} must belong to {} in env.roledefs.'.format(host_name, role))

    openstack_nodes = set(env.roledefs.get('openstack', []))
    cfgm_nodes = set(env.roledefs.get('cfgm', []))
    database_nodes = set(env.roledefs.get('database', []))

    if cfgm_nodes != database_nodes:
        if database_nodes.issubset(cfgm_nodes):
            role_msgs.append('ERROR: database nodes cannot be subset of cfgm nodes.')
        elif cfgm_nodes.issubset(database_nodes):
            role_msgs.append('ERROR: cfgm nodes cannot be subset of database nodes.')

    _print_message(role_msgs)

    print('\n{:=^80}'.format(' Check network connectivity '))
    if conn_check == 'yes':
        print('\n>>> Testing management network connectivity from host build.')
    build_ping_msgs = []
    build_ping_results = {}
    build_ping_rows = []
    build_ping_headers = ['From', 'To', 'Target IP', 'Result']
    for host_string in host_strings:
        host_name = _hstr_to_name(host_string)
        mgmt_ip = _hstr_to_ip(host_string)
        if conn_check == 'yes':
            result, msg = _ping_hstr(env.roledefs['build'][0], host_string)
            build_ping_msgs.append(msg)
            _update_progress(host_string, host_strings)
        else:
            result = '-'
        build_ping_results[host_string] = result
        build_ping_rows.append(['host_build', host_name, mgmt_ip, result])
    _print_table(build_ping_headers, build_ping_rows, title='Management Network Connectivity Check')
    _print_message(build_ping_msgs)

    if conn_check == 'yes':
        print('\n>>> Testing connectivity to a config node.')
    cfgm_ping_msgs = []
    cfgm_ping_rows = []
    cfgm_ping_headers = ['From', 'To', 'Target IP', 'Result']
    for host_string in host_strings:
        cfgm_tgt_name = _hstr_to_name(env.roledefs['cfgm'][0])
        cfgm_tgt_ip = _hstr_to_ip(env.roledefs['cfgm'][0])
        if env.roledefs['cfgm'][0] in control_data:
            cfgm_tgt_ip = control_data[env.roledefs['cfgm'][0]]['ip'].split('/')[0]

        # After the controller setup, you can use internal vip as a target address.
        #
        # if env_ha.get('contrail_internal_vip'):
        #    cfgm_tgt_ip = env_ha['contrail_internal_vip']
        #    cfgm_tgt_name = 'contrail_internal_vip'
        # elif env_ha.get('internal_vip'):
        #    cfgm_tgt_ip = env_ha['internal_vip']
        #    cfgm_tgt_name = 'internal_vip'

        host_name = _hstr_to_name(host_string)
        if build_ping_results[host_string] == 'OK':
            result, msg = _ping_hstr(host_string, cfgm_tgt_ip, use_ctrl=True)
            cfgm_ping_msgs.append(msg)
            _update_progress(host_string, host_strings)
        else:
            result = '-'
        cfgm_ping_rows.append([host_name, cfgm_tgt_name, cfgm_tgt_ip, result])
    _print_table(cfgm_ping_headers, cfgm_ping_rows, title='Discovery Connectivity Check')
    _print_message(cfgm_ping_msgs)

    # For dedicated control setup, the control connectivity should be checked.
    if set(env.roledefs.get('cfgm', [])) != set(env.roledefs.get('control', [])):
        if conn_check == 'yes':
            print('\n>>> Testing connectivity to a control node.')
        ctrl_hstr = env.roledefs['control'][0]
        ctrl_tgt_name = _hstr_to_name(ctrl_hstr)
        ctrl_tgt_ip = _hstr_to_ip(ctrl_hstr)
        if ctrl_hstr in control_data:
            ctrl_tgt_ip = control_data[ctrl_hstr]['ip'].split('/')[0]

        ctrl_ping_msgs = []
        ctrl_ping_rows = []
        ctrl_ping_headers = ['From', 'To', 'Target IP', 'Result']
        for host_string in host_strings:
            host_name = _hstr_to_name(host_string)
            if build_ping_results[host_string] == 'OK':
                result, msg = _ping_hstr(host_string, ctrl_tgt_ip, use_ctrl=True)
                ctrl_ping_msgs.append(msg)
                _update_progress(host_string, host_strings)
            else:
                result = '-'
            ctrl_ping_rows.append([host_name, ctrl_tgt_name, ctrl_tgt_ip, result])
        _print_table(ctrl_ping_headers, ctrl_ping_rows, title='Control Connectivity Check')
        _print_message(ctrl_ping_msgs)

    # For dedicated collector setup, the collector connectivity should be checked.
    if set(env.roledefs.get('cfgm', [])) != set(env.roledefs.get('collector', [])):
        if conn_check == 'yes':
            print('\n>>> Testing connectivity to a collector node.')
        col_hstr = env.roledefs['collector'][0]
        col_tgt_name = _hstr_to_name(col_hstr)
        col_tgt_ip = _hstr_to_ip(col_hstr)
        if col_hstr in control_data:
            col_tgt_ip = control_data[col_hstr]['ip'].split('/')[0]

        col_ping_msgs = []
        col_ping_rows = []
        col_ping_headers = ['From', 'To', 'Target IP', 'Result']
        for host_string in host_strings:
            host_name = _hstr_to_name(host_string)
            if build_ping_results[host_string] == 'OK':
                result, msg = _ping_hstr(host_string, col_tgt_ip, use_ctrl=True)
                col_ping_msgs.append(msg)
                _update_progress(host_string, host_strings)
            else:
                result = '-'
            col_ping_rows.append([host_name, col_tgt_name, col_tgt_ip, result])
        _print_table(col_ping_headers, col_ping_rows, title='Collector Connectivity Check')
        _print_message(col_ping_msgs)

    print('\n{:=^80}'.format(' Check host configuration '))
    host_msgs = []
    host_rows = []
    host_headers = ['Hostname', 'Management IP', 'Control-Data IP', 'env.hostnames',
                    'env.ostypes', 'control_data']
    for host_string in host_strings:
        mgmt_ip = _hstr_to_ip(host_string)
        ctrl_ip = _hstr_to_ctrl(host_string) or '-'
        host_name = _hstr_to_name(host_string)

        # With multiple interface setup, nodes should have control_data entry.
        if control_data and host_string not in control_data:
            host_msgs.append('WARNING: {} has no control-data address.'.format(host_name))

        if host_string not in env_hostnames:
            host_msgs.append("ERROR: {} must have hostname definition in env.hostnames.".format(host_name))

        if not env_key_filename and host_string not in env_passwords:
            host_msgs.append("ERROR: {} must have password definition in env.passwords.".format(host_name))

        if build_ping_results[host_string] == 'OK':
            with settings(host_string=host_string, warn_only=True):
                hostname = sudo('hostname')
                if host_name != hostname:
                    hostname_check = 'NG'
                    host_msgs.append('ERROR: Hostname of {} is {}.'.format(host_string, hostname))
                else:
                    hostname_check = 'OK'

                os_type = env_ostypes.get(host_string)
                if os_type == 'ubuntu':
                    if sudo('test -e /etc/lsb-release').failed:
                        os_check = 'NG'
                        host_msgs.append('ERROR: {} is not ubuntu host.'.format(host_name))
                    else:
                        os_check = 'OK'
                elif os_type in ['redhat', 'centos']:
                    if sudo('test -e /etc/redhat-release').failed:
                        os_check = 'NG'
                        host_msgs.append('ERROR: {} is not redhat/centos host.'.format(host_name))
                    else:
                        os_check = 'OK'
                else:
                    os_check = '-'

                if host_string in control_data:
                    ctrl_ip = control_data[host_string]['ip']
                    ctrl_ip_check = 'NG'
                    if sudo('ip addr | grep " {} "'.format(ctrl_ip)).succeeded:
                        ctrl_ip_check = 'OK'
                    else:
                        host_msgs.append('ERROR: {} is not allocated to {}.'.format(ctrl_ip, host_name))
                else:
                    ctrl_ip_check = '-'
        else:
            hostname_check = '-'
            os_check = '-'
            ctrl_ip_check = '-'
        host_rows.append([host_name, mgmt_ip, ctrl_ip, hostname_check, os_check, ctrl_ip_check])
    _print_table(host_headers, host_rows, title='Host Property Check')

    ctrl_ips = [v['ip'].split('/')[0] for v in control_data.values()]
    dup_ctrl_ips = [k for k, v in Counter(ctrl_ips).items() if v > 1]
    if dup_ctrl_ips:
        host_msgs.append('ERROR: Duplicated control_data address: {}'.format(' '.join(dup_ctrl_ips)))

    _print_message(host_msgs)

    route_msgs = []
    route_rows = []
    route_headers = ['Hostname', 'Static Route', 'Exist']
    for host_string in host_strings:
        host_name = _hstr_to_name(host_string)
        for route in static_route.get(host_string, []):
            ip_prefix = route['ip'] + '/' + str(IPAddress(route['netmask']).netmask_bits())
            gw = route['gw']
            intf = route['intf']
            route_entry = '{} via {} dev {}'.format(ip_prefix, gw, intf)
            route_check = 'NO'
            if build_ping_results[host_string] == 'OK':
                with settings(host_string=host_string, warn_only=True):
                    if sudo('ip link show vhost0').succeeded:
                        route_entry = '{} via {} dev vhost0'.format(ip_prefix, gw)
                    if sudo('ip route show | grep ^"{}\s*"$'.format(route_entry)).failed:
                        msg = 'ERROR: Route is not configured on {} : {}'.format(host_name, route_entry)
                        route_msgs.append(msg)
                    else:
                        route_check = 'YES'
            else:
                route_check = '-'
            route_rows.append([host_name, route_entry, route_check])

    # With multiple interface setup, nodes should have static route entries.
    for host_string in control_data.keys():
        if static_route and host_string not in static_route:
            host_name = _hstr_to_name(host_string)
            msg = 'WARNING: {} has control-data address, but no static route entry.'.format(host_name)
            route_msgs.append(msg)

    if static_route:
        _print_table(route_headers, route_rows, title='Static Routes Check')
        _print_message(route_msgs)

    print('\n{:=^80}'.format(' Check tor-agent configuration '))
    tor_msgs = []
    tor_consistency = {}
    tor_dict = OrderedDict()
    for host_string in env_tor_agent.keys():
        for tor_agent in env.tor_agent[host_string]:
            tor_id = tor_agent.get('tor_id', '-')
            tor_agent_id = tor_agent.get('tor_agent_id', tor_id)
            tor_tsn_name = tor_agent.get('tor_tsn_name')
            tor_name = tor_agent.get('tor_name')
            tor_agent_name = '{}-{}'.format(tor_tsn_name, tor_agent_id)
            tor_agent_name = tor_agent.get('tor_agent_name', tor_agent_name)
            tor_consistency[tor_name] = '-'
            if tor_name not in tor_dict.keys():
                tor_dict[tor_name] = tor_agent.copy()
                tor_dict[tor_name].pop('tor_tsn_ip', None)
                tor_dict[tor_name].pop('tor_tsn_name', None)
                tor_dict[tor_name]['tsn_names'] = [tor_tsn_name]
            else:
                for k, v in tor_agent.items():
                    if k in ['tor_tsn_ip', 'tor_tsn_name']:
                        continue
                    if tor_dict[tor_name].get(k) != v:
                        tor_msgs.append('ERROR: {} for {} is not consistent for HA.'.format(k, tor_agent_name))
                        tor_consistency[tor_name] = 'NG'
                if tor_consistency[tor_name] == '-':
                    tor_consistency[tor_name] = 'OK'
                tor_dict[tor_name]['tsn_names'].append(tor_tsn_name)

    tor_rows = []
    tor_headers = ['TSN Name', 'ToR Agent Name', 'ToR Name', 'TSN Consistency', 'HA Consistency', ]
    for host_string in env_tor_agent.keys():
        tsn_ctrl_ip = _hstr_to_ctrl(host_string) or _hstr_to_ip(host_string)
        tsn_name = _hstr_to_name(host_string)
        for tor_agent in env.tor_agent[host_string]:
            tor_id = tor_agent.get('tor_id', '-')
            tor_agent_id = tor_agent.get('tor_agent_id', tor_id)
            if tor_agent_id != '-':
                tor_agent_id = int(tor_agent_id)
            tor_tsn_name = tor_agent.get('tor_tsn_name')
            tor_tsn_ip = tor_agent.get('tor_tsn_ip')
            tor_name = tor_agent.get('tor_name')
            tor_agent_name = '{}-{}'.format(tor_tsn_name, tor_agent_id)
            tor_agent_name = tor_agent.get('tor_agent_name', tor_agent_name)
            tsn_consistency = 'OK'
            if tor_tsn_name != tsn_name:
                tor_msgs.append("ERROR: tor_tsn_name of {} should be {}.".format(tor_agent_name, tsn_name))
                tsn_consistency = 'NG'
            if tor_tsn_ip != tsn_ctrl_ip:
                tor_msgs.append("ERROR: tor_tsn_ip of {} should be {}.".format(tor_agent_name, tsn_ctrl_ip))
                tsn_consistency = 'NG'
            ha_consistency = tor_consistency[tor_name]
            if len(tor_dict[tor_name]['tsn_names']) > 2:
                tor_msgs.append('WARNING: {} is associated with more than two TSNs.'.format(tor_name))
            elif len(env.roledefs['tsn']) > 1 and len(tor_dict[tor_name]['tsn_names']) < 2:
                tor_msgs.append('WARNING: {} has no redundancy.'.format(tor_name))
            tor_rows.append([tsn_name, tor_agent_name, tor_name, tsn_consistency, ha_consistency])
    _print_table(tor_headers, sorted(tor_rows), title='ToR Agent Consistency Check')
    _print_message(tor_msgs)

    print('\n{:=^80}'.format(' Check TSN tunnel IP connectivity '))
    if conn_check == 'yes':
        print('\n>>> Testing control-data network connectivity from TSN.')
    tunnel_ping_msgs = []
    tunnel_rows = []
    tunnel_headers = ['From', 'To', 'Type', 'Target IP', 'Result']
    for host_string, tor_agents in env_tor_agent.items():
        tsn_name = _hstr_to_name(host_string)
        for tor_agent in tor_agents:
            tor_name = tor_agent.get('tor_name')
            tunnel_ip = tor_agent.get('tor_tunnel_ip')
            if build_ping_results.get(host_string) == 'OK' and tunnel_ip:
                result, msg = _ping_hstr(host_string, tunnel_ip, use_ctrl=True)
                tunnel_ping_msgs.append(msg)
            else:
                result = '-'
            tunnel_rows.append([tsn_name, tor_name, 'ToR Switch', tunnel_ip, result])

        for tgt_compute in env.roledefs.get('compute', []):
            if tgt_compute == host_string:
                continue
            elif tgt_compute in env.roledefs.get('tsn', []):
                node_type = 'TSN'
            else:
                node_type = 'Compute'
            tgt_name = _hstr_to_name(tgt_compute)
            tgt_ip = _hstr_to_ctrl(tgt_compute) or _hstr_to_ip(tgt_compute)
            if build_ping_results.get(host_string) == 'OK':
                result, msg = _ping_hstr(host_string, tgt_ip, use_ctrl=True)
                tunnel_ping_msgs.append(msg)
            else:
                result = '-'
            tunnel_rows.append([tsn_name, tgt_name, node_type, tgt_ip, result])
        if build_ping_results.get(host_string) == 'OK':
            _update_progress(host_string, env_tor_agent.keys())
    _print_table(tunnel_headers, tunnel_rows, title='Tunnel IP Connectivity Check')

    print('\n{:=^80}'.format(' Check HA configuration '))
    ha_msgs = []
    ha_defaults = OrderedDict()
    ha_defaults['internal_vip'] = None
    ha_defaults['external_vip'] = None
    ha_defaults['internal_virtual_router_id'] = 100
    ha_defaults['external_virtual_router_id'] = 100
    ha_defaults['contrail_internal_vip'] = None
    ha_defaults['contrail_external_vip'] = None
    ha_defaults['contrail_internal_virtual_router_id'] = 100
    ha_defaults['contrail_external_virtual_router_id'] = 100
    if env_ha.get('collector_external_vip'):
        ha_defaults['collector_external_vip'] = None
    if env_ha.get('collector_internal_vip'):
        ha_defaults['collector_internal_vip'] = None
    if env_ha.get('collector_external_virtual_router_id'):
        ha_defaults['collector_external_virtual_router_id'] = None
    if env_ha.get('collector_internal_virtual_router_id'):
        ha_defaults['collector_internal_virtual_router_id'] = None
    if env_ha.get('v1_contrail_internal_vip'):
        ha_defaults['v1_contrail_internal_vip'] = None
    if env_ha.get('v1_contrail_external_vip'):
        ha_defaults['v1_contrail_external_vip'] = None
    if env_ha.get('v1_contrail_internal_virtual_router_id'):
        ha_defaults['v1_contrail_internal_virtual_router_id'] = 100
    if env_ha.get('v1_contrail_external_virtual_router_id'):
        ha_defaults['v1_contrail_external_virtual_router_id'] = 100
    ha_defaults['haproxy_token'] = None
    ha_defaults['nfs_server'] = env.roledefs.get('compute', ['-'])[0]
    ha_defaults['nfs_glance_path'] = '/var/tmp/glance-images/'
    _print_env_dict(env_ha, ha_defaults, title='HA Parameter Check')
    print('')

    if (len(openstack_nodes) > 1 or len(cfgm_nodes) > 1) and not env_ha:
        ha_msgs.append('WARNING: env.ha is not defined in testbed.py.')

    internal_vip = env_ha.get('internal_vip')
    external_vip = env_ha.get('external_vip')
    contrail_internal_vip = env_ha.get('contrail_internal_vip')
    contrail_external_vip = env_ha.get('contrail_external_vip')
    contrail_internal_vrid = env_ha.get('contrail_internal_virtual_router_id')
    contrail_external_vrid = env_ha.get('contrail_external_virtual_router_id')
    collector_internal_vip = env_ha.get('collector_internal_vip')
    collector_external_vip = env_ha.get('collector_external_vip')
    collector_internal_vrid = env_ha.get('collector_internal_virtual_router_id')
    collector_external_vrid = env_ha.get('collector_external_virtual_router_id')
    v1_internal_vip = env_ha.get('v1_contrail_internal_vip')
    v1_external_vip = env_ha.get('v1_contrail_external_vip')
    v1_internal_vrid = env_ha.get('v1_contrail_internal_virtual_router_id')
    v1_external_vrid = env_ha.get('v1_contrail_external_virtual_router_id')

    if len(openstack_nodes) > 1 and not internal_vip:
        ha_msgs.append('ERROR: internal_vip must be defined for multiple openstack setup.')

    if len(openstack_nodes) > 1 and list(openstack_nodes)[0] in control_data and not external_vip:
        ha_msgs.append('ERROR: external_vip must be defined for multiple openstack setup.')

    if len(openstack_nodes) > 1 and external_vip:
        for host_string in env.roledefs['openstack']:
            if host_string not in control_data:
                host_name = _hstr_to_name(host_string)
                ha_msgs.append('ERROR: {} must have control_data address.'.format(host_name))

    if openstack_nodes != cfgm_nodes:
        if len(cfgm_nodes) > 1 and not contrail_internal_vip:
            ha_msgs.append('ERROR: contrail_internal_vip must be defined for multiple cfgm setup.')

        if len(cfgm_nodes) > 1 and list(cfgm_nodes)[0] in control_data and not contrail_external_vip:
            ha_msgs.append('ERROR: contrail_external_vip must be defined for multiple cfgm setup.')

        if len(cfgm_nodes) > 1 and contrail_external_vip:
            for host_string in env.roledefs['cfgm']:
                if host_string not in control_data:
                    host_name = _hstr_to_name(host_string)
                    ha_msgs.append('ERROR: {} must have control_data address.'.format(host_name))
    else:
        if contrail_internal_vip:
            ha_msgs.append('ERROR: contrail_internal_vip should be removed.')

        if contrail_external_vip:
            ha_msgs.append('ERROR: contrail_external_vip should be removed.')

    if v1_internal_vip:
        if v1_internal_vip == contrail_internal_vip:
            ha_msgs.append('ERROR: Internal VIPs on V1 and V2 cluster must be different.')
        if v1_internal_vrid == contrail_internal_vrid:
            ha_msgs.append('WARNING: Internal VRIDs on V1 and V2 cluster must be different '
                           'if both are connected with the same subnet.')

    if v1_external_vip:
        if v1_external_vip == contrail_external_vip:
            ha_msgs.append('ERROR: External VIPs on V1 and V2 cluster must be different.')
        if v1_external_vrid == contrail_external_vrid:
            ha_msgs.append('WARNING: External VRIDs on V1 and V2 cluster must be different '
                           'if both are connected with the same subnet.')

    if collector_internal_vip:
        if collector_internal_vip == contrail_internal_vip:
            ha_msgs.append('ERROR: Internal VIPs on config and collector must be different.')
        if collector_internal_vrid == contrail_internal_vrid:
            ha_msgs.append('WARNING: Internal VRIDs on config and collector must be different '
                           'if both are connected with the same subnet.')

    if collector_external_vip:
        if collector_external_vip == contrail_external_vip:
            ha_msgs.append('ERROR: External VIPs on config and collector must be different.')
        if collector_external_vrid == contrail_external_vrid:
            ha_msgs.append('WARNING: External VRIDs on config and collector must be different '
                           'if both are connected with the same subnet.')
    _print_message(ha_msgs)


def pre_check_testbed():
    """
    By adding the following code block to __init__.py, this function runs before every fab tasks.

    /opt/contrail/utils/fabfile/__init__.py
    ------------------------------------------------------------------------
    enable_validation = True
    try:
        from tasks.verify_testbed import *
    except ImportError:
        enable_validation = False

    if enable_validation and env.tasks:
        exclude_tasks = ['verify_testbed', 'show_testbed']
        run_task =  env.tasks[0].split(':')[0]
        if run_task not in exclude_tasks:
            execute(pre_check_testbed, host=env.roledefs['build'][0])
    ------------------------------------------------------------------------
    """
    abort_msg = 'A problem was detected with testbed.py.\n\n'

    target_roles = ['cfgm', 'control', 'collector', 'database', 'webui', 'compute', 'tsn', 'toragent']
    host_strings = _get_role_members(target_roles)

    # === Check variables ===

    # Add necessary variables for your environment.
    required_vars = ['env.roledefs', 'env.hostnames', 'env.passwords', 'env.ostypes']
    # required_vars = ['env.roledefs', 'env.hostnames']

    for var in required_vars:
        error_msg = '{} is not defined.'.format(var)
        if var.split('.')[0] == 'env':
            if not getattr(env, var.split('.')[-1], None):
                abort(abort_msg + error_msg)
        else:
            if not getattr(testbed, var, None):
                abort(abort_msg + error_msg)

    env_key_filename = getattr(env, 'key_filename', None)
    env_passwords = getattr(env, 'passwords', {})
    env_ostypes = getattr(env, 'ostypes', {})
    control_data = getattr(testbed, 'control_data', {})
    env_tor_agent = getattr(env, 'tor_agent', {})

    if 'all' in env.hostnames:
        if len(env.roledefs['all']) != len(env.hostnames['all']):
            error_msg = "Length of 'all' in env.roledefs and env.hostnames are not equal."
            abort(abort_msg + error_msg)
        env_hostnames = dict(zip(env.roledefs['all'], env.hostnames['all']))
    else:
        env_hostnames = env.hostnames

    # === Check role assignment ===

    # Add necessary roles for your environment.
    required_roles = ['all', 'cfgm', 'control', 'collector', 'database', 'webui', 'build']
    required_roles += ['openstack', 'compute']
    required_roles += ['tsn', 'toragent']
    # required_roles += ['storage-master', 'storage-compute']
    # required_roles += ['oldcfgm', 'oldcontrol', 'oldcollector', 'olddatabase', 'oldwebui', 'oldbuild']

    role_msgs = []
    for role in required_roles:
        if role not in env.roledefs:
            error_msg = '{} is not defined in env.roledefs.'.format(role)
            abort(abort_msg + error_msg)

    for host_string in env_tor_agent.keys():
        host_name = _hstr_to_name(host_string)
        for role in ['compute', 'tsn', 'toragent']:
            if host_string not in env.roledefs.get(role, []):
                error_msg = '{} must belong to {} in env.roledefs.'.format(host_name, role)
                abort(abort_msg + error_msg)

    openstack_nodes = set(env.roledefs.get('openstack', []))
    cfgm_nodes = set(env.roledefs.get('cfgm', []))
    database_nodes = set(env.roledefs.get('database', []))

    if cfgm_nodes != database_nodes:
        if database_nodes.issubset(cfgm_nodes):
            error_msg = 'database nodes cannot be subset of cfgm nodes.'
            abort(abort_msg + error_msg)
        elif cfgm_nodes.issubset(database_nodes):
            error_msg = 'cfgm nodes cannot be subset of database nodes.'
            abort(abort_msg + error_msg)

    # === Check host configuration ===
    for host_string in host_strings:
        if host_string not in env_hostnames:
            error_msg = '{} is not defined in env.hostnames.'.format(host_string)
            abort(abort_msg + error_msg)

        if not env_key_filename and host_string not in env_passwords:
            error_msg = '{} is not defined in env.passwords.'.format(host_string)
            abort(abort_msg + error_msg)

        if host_string not in env_ostypes:
            error_msg = '{} is not defined in env.ostypes.'.format(host_string)
            # abort(abort_msg + error_msg)

    ctrl_ips = [v['ip'].split('/')[0] for v in control_data.values()]
    dup_ctrl_ips = [k for k, v in Counter(ctrl_ips).items() if v > 1]
    if dup_ctrl_ips:
        error_msg = 'Duplicated control_data address: {}'.format(' '.join(dup_ctrl_ips))
        abort(abort_msg + error_msg)

    # === Check tor-agent definition ===
    tor_dict = OrderedDict()
    for host_string in env_tor_agent.keys():
        for tor_agent in env_tor_agent[host_string]:
            tor_tsn_ip = tor_agent.get('tor_tsn_ip')
            tor_name = tor_agent.get('tor_name')
            tor_tsn_name = tor_agent.get('tor_tsn_name')
            tor_id = tor_agent.get('tor_id', '')
            tor_agent_id = tor_agent.get('tor_agent_id', tor_id)
            tor_agent_name = '{}-{}'.format(tor_tsn_name, tor_agent_id)
            tor_agent_name = tor_agent.get('tor_agent_name', tor_agent_name)
            if tor_name not in tor_dict:
                tor_dict[tor_name] = tor_agent.copy()
                tor_dict[tor_name].pop('tor_tsn_ip', None)
                tor_dict[tor_name].pop('tor_tsn_name', None)
                tor_dict[tor_name]['tsn_names'] = [tor_tsn_name]
            else:
                tor_dict[tor_name]['tsn_names'].append(tor_tsn_name)
                for k, v in tor_agent.items():
                    if k in ['tor_tsn_ip', 'tor_tsn_name']:
                        continue
                    if tor_dict[tor_name].get(k) != v:
                        error_msg = '{} for {} is not consistent with HA pair.'.format(k, tor_agent_name)
                        abort(abort_msg + error_msg)
                if len(tor_dict[tor_name]['tsn_names']) > 2:
                    error_msg = '{} is associated with more than 2 TSNs.'.format(tor_name)
                    abort(abort_msg + error_msg)
            tsn_ctrl_ip = _hstr_to_ctrl(host_string) or _hstr_to_ip(host_string)
            if tor_tsn_ip != tsn_ctrl_ip:
                error_msg = "tor_tsn_ip for {} should be {}.".format(tor_agent_name, tsn_ctrl_ip)
                abort(abort_msg + error_msg)
            tsn_name = _hstr_to_name(host_string)
            if tor_tsn_name != tsn_name:
                error_msg = "tor_tsn_name for {} should be {}.".format(tor_agent_name, tsn_name)
                abort(abort_msg + error_msg)

    # === Check HA configuration ===

    env_ha = getattr(env, 'ha', {})
    internal_vip = env_ha.get('internal_vip')
    external_vip = env_ha.get('external_vip')
    contrail_internal_vip = env_ha.get('contrail_internal_vip')
    contrail_external_vip = env_ha.get('contrail_external_vip')
    contrail_internal_vrid = env_ha.get('contrail_internal_virtual_router_id')
    contrail_external_vrid = env_ha.get('contrail_external_virtual_router_id')
    collector_internal_vip = env_ha.get('collector_internal_vip')
    collector_external_vip = env_ha.get('collector_external_vip')
    collector_internal_vrid = env_ha.get('collector_internal_virtual_router_id')
    collector_external_vrid = env_ha.get('collector_external_virtual_router_id')
    v1_internal_vip = env_ha.get('v1_contrail_internal_vip')
    v1_external_vip = env_ha.get('v1_contrail_external_vip')
    v1_internal_vrid = env_ha.get('v1_contrail_internal_virtual_router_id')
    v1_external_vrid = env_ha.get('v1_contrail_external_virtual_router_id')

    if len(openstack_nodes) > 1 and not internal_vip:
        error_msg = 'internal_vip must be defined for multiple openstack setup.'
        abort(abort_msg + error_msg)

    if len(openstack_nodes) > 1 and list(openstack_nodes)[0] in control_data and not external_vip:
        error_msg = 'external_vip must be defined for multiple openstack setup.'
        abort(abort_msg + error_msg)

    if len(openstack_nodes) > 1 and external_vip:
        for host_string in env.roledefs['openstack']:
            if not control_data.get(host_string):
                host_name = _hstr_to_name(host_string)
                error_msg = '{} must have control_data address.'.format(host_name)
                abort(abort_msg + error_msg)

    if openstack_nodes != cfgm_nodes:
        if len(cfgm_nodes) > 1 and not contrail_internal_vip:
            error_msg = 'contrail_internal_vip must be defined for multiple cfgm setup.'
            abort(abort_msg + error_msg)

        if len(cfgm_nodes) > 1 and list(cfgm_nodes)[0] in control_data and not contrail_external_vip:
            error_msg = 'contrail_external_vip must be defined for multiple cfgm setup.'
            abort(abort_msg + error_msg)

        if len(cfgm_nodes) > 1 and contrail_external_vip:
            for host_string in env.roledefs['cfgm']:
                if not control_data.get(host_string):
                    host_name = _hstr_to_name(host_string)
                    error_msg = '{} must have control_data address.'.format(host_name)
                    abort(abort_msg + error_msg)
    else:
        if contrail_internal_vip:
            error_msg = 'contrail_internal_vip should be removed.'
            abort(abort_msg + error_msg)

        if contrail_external_vip:
            error_msg = 'contrail_external_vip should be removed.'
            abort(abort_msg + error_msg)

    # Check VIPs for ISSU
    if v1_internal_vip:
        if v1_internal_vip == contrail_internal_vip:
            error_msg = 'Internal VIPs on V1 and V2 cluster must be different.'
            abort(abort_msg + error_msg)
        # If V1 and V2 cluster are connected with the same subnet, enable following checks.
        if v1_internal_vrid == contrail_internal_vrid:
            error_msg = 'Internal VRIDs on V1 and V2 cluster must be different.'
            # abort(abort_msg + error_msg)

    if v1_external_vip:
        if v1_external_vip == contrail_external_vip:
            error_msg = 'External VIPs on V1 and V2 cluster must be different.'
            abort(abort_msg + error_msg)
        # If V1 and V2 cluster are connected with the same subnet, enable following checks.
        if v1_external_vrid == contrail_external_vrid:
            error_msg = 'External VRIDs on V1 and V2 cluster must be different.'
            # abort(abort_msg + error_msg)

    if collector_internal_vip:
        if collector_internal_vip == contrail_internal_vip:
            error_msg = 'Internal VIPs on config and collector must be different.'
            abort(abort_msg + error_msg)
        # If cfgm and collector nodes are connected with the same subnet, enable following checks.
        if collector_internal_vrid == contrail_internal_vrid:
            error_msg = 'Internal VRIDs on config and collector must be different.'
            # abort(abort_msg + error_msg)

    if collector_external_vip:
        if collector_external_vip == contrail_external_vip:
            error_msg = 'External VIPs on config and collector must be different.'
            abort(abort_msg + error_msg)
        # If cfgm and collector nodes are connected with the same subnet, enable following checks.
        if collector_external_vrid == contrail_external_vrid:
            error_msg = 'External VRIDs on config and collector must be different.'
            # abort(abort_msg + error_msg)

    # User defined check items
    pass

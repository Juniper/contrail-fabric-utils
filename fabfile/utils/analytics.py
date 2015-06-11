from fabfile.config import testbed
from fabfile.utils.fabos import detect_ostype, get_openstack_sku
from fabfile.utils.cluster import get_orchestrator

def get_collector_syslog_port():
    env_obj = getattr(testbed, 'env')
    rsyslog_dict = getattr(env_obj, 'rsyslog_params', None)

    if ((rsyslog_dict is not None) and
            (rsyslog_dict['status'].lower() == 'enable')):
        if 'port' in rsyslog_dict:
            return rsyslog_dict['port']
        else:
            return 19876  # default port number.
    else:
        return None
# end get_collector_syslog_port

def get_database_ttl():
    return getattr(testbed, 'database_ttl', None)
#end get_database_ttl

def get_database_dir():
    return getattr(testbed, 'database_dir', None)

def get_analytics_data_dir():
    return getattr(testbed, 'analytics_data_dir', None)

def get_ssd_data_dir():
    return getattr(testbed, 'ssd_data_dir', None)

def get_redis_password():
    return getattr(testbed, 'redis_password', None)
#end get_database_dir

def get_analytics_config_audit_ttl():
    return getattr(testbed, 'analytics_config_audit_ttl', None)
#end get_analytics_config_audit_ttl

def get_analytics_statistics_ttl():
    return getattr(testbed, 'analytics_statistics_ttl', None)
#end get_analytics_statistics_ttl

def get_analytics_flow_ttl():
    return getattr(testbed, 'analytics_flow_ttl', None)
#end get_analytics_flow_ttl

def get_minimum_diskGB():
    return getattr(testbed, 'minimum_diskGB', '256')
#end get_analytics_flow_ttl

def get_kafka_enabled():
    return getattr(testbed, 'kafka_enabled', True)

def get_enable_ceilometer():
    return getattr(testbed, 'enable_ceilometer', False)
#end get_enable_ceilometer

def is_ceilometer_supported(use_install_repo=False):
    # Ceilometer should be enabled
    enable_ceilometer = get_enable_ceilometer()
    if not enable_ceilometer:
        return False
    # Orchestrator should be openstack
    orchestrator = get_orchestrator()
    if orchestrator != 'openstack':
        return False
    # Currently supported only on ubuntu icehouse
    os_type = detect_ostype()
    openstack_sku = get_openstack_sku(use_install_repo)
    if os_type in ['redhat'] and \
            openstack_sku in ['juno']:
        return True
    elif os_type in ['ubuntu'] and \
            openstack_sku in ['juno']:
        return True
    else:
        return False
#end is_ceilometer_supported

def is_ceilometer_install_supported(use_install_repo=False):
    supported = is_ceilometer_supported(use_install_repo)
    if not supported:
        return False
    # Not supported on redhat
    os_type = detect_ostype()
    if os_type == 'redhat':
        return False
    return supported
#end is_ceilometer_install_supported

def is_ceilometer_provision_supported(use_install_repo=False):
    supported = is_ceilometer_supported(use_install_repo)
    if not supported:
        return False
    # Not supported on redhat
    os_type = detect_ostype()
    if os_type == 'redhat':
        return False
    return supported
#end is_ceilometer_provision_supported

def is_ceilometer_contrail_plugin_install_supported():
    return is_ceilometer_supported()
#end is_ceilometer_contrail_plugin_install_supported

def is_ceilometer_contrail_plugin_provision_supported():
    return is_ceilometer_supported()
#end is_ceilometer_contrail_plugin_provision_supported

def is_ceilometer_compute_install_supported():
    supported = is_ceilometer_supported()
    if not supported:
        return False
    # Not supported on redhat
    os_type = detect_ostype()
    if os_type == 'redhat':
        return False
    return supported
#end is_ceilometer_compute_install_supported

def is_ceilometer_compute_provision_supported():
    supported = is_ceilometer_supported()
    if not supported:
        return False
    # Not supported on redhat
    os_type = detect_ostype()
    if os_type == 'redhat':
        return False
    return supported
#end is_ceilometer_compute_provision_supported

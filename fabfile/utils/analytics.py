from fabfile.config import testbed

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

def get_analytics_protobuf_port():
    return getattr(testbed, 'analytics_protobuf_port', None)
#end get_analytics_protobuf_port

def get_database_ttl():
    return getattr(testbed, 'database_ttl', None)
#end get_database_ttl

def get_database_dir():
    return getattr(testbed, 'database_dir', None)

def get_analytics_data_dir():
    return getattr(testbed, 'analytics_data_dir', None)

def get_ssd_data_dir():
    return getattr(testbed, 'ssd_data_dir', None)
#end get_database_dir

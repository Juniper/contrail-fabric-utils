from fabfile.config import testbed

def get_collector_syslog_port():
    try:
        testbed.env.rsyslog_params
        if testbed.env.rsyslog_params['status'].lower() == 'enable':
            try:
                return testbed.env.rsyslog_params['port']
            except:
                return 8765  # default port number.
        else:
            return None
    except:
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
#end get_database_dir

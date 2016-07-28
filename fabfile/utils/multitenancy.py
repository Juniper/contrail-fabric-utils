from fabfile.config import testbed
from fabric.api import env
from fabfile.utils.host import *

def get_mt_enable():
    return getattr(testbed, 'multi_tenancy', True)
#end _get_mt_ena

def get_analytics_aaa_mode():
    return getattr(testbed, 'analytics_aaa_mode', 'cloud-admin-only')
# end get_analytics_mt_enable

def get_mt_opts():
    mt_opts = ''
    if get_mt_enable():
        u, p = get_authserver_credentials()
        t = get_admin_tenant_name()
        if not u or not p or not t:
            raise Exception('Admin user, password and tenant must be defined if multi tenancy is enabled')
        mt_opts = " --admin_user %s --admin_password %s --admin_tenant_name %s" %(u, p, t)
    return mt_opts

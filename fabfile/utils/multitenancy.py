from fabfile.config import testbed
from fabric.api import env
from fabfile.utils.host import *

def get_mt_enable():
    return getattr(testbed, 'multi_tenancy', True)
#end _get_mt_ena

def get_mt_opts():
    mt_opts = ''
    if get_mt_enable():
        u = get_keystone_admin_user()
        p = get_keystone_admin_password()
        t = get_keystone_admin_tenant_name()
        if not u or not p or not t:
            raise Exception('Admin user, password and tenant must be defined if multi tenancy is enabled')
        mt_opts = " --admin_user %s --admin_password %s --admin_tenant_name %s" %(u, p, t)
    return mt_opts

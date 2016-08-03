from fabfile.config import testbed
from fabric.api import env
from fabfile.utils.host import *

def is_auth_reqd():
    mt = getattr(testbed, 'multi_tenancy', None)
    aaa_mode = getattr(testbed, 'aaa_mode', None)
    auth_needed = True
    if mt is not None:
        auth_needed = mt
    elif aaa_mode is not None:
        auth_needed = aaa_mode != "no-auth"
    return auth_needed

def get_mt_enable():
    return is_auth_reqd()

def get_analytics_aaa_mode():
    return getattr(testbed, 'analytics_aaa_mode', 'cloud-admin')
# end get_analytics_mt_enable

def get_cloud_admin_role():
    return getattr(testbed, 'cloud_admin_role', '')

def get_mt_opts():
    mt_opts = ''
    if is_auth_reqd():
        u, p = get_authserver_credentials()
        t = get_admin_tenant_name()
        if not u or not p or not t:
             raise Exception('Admin user, password and tenant must be defined if multi tenancy is enabled')
        mt_opts = " --admin_user %s --admin_password %s --admin_tenant_name %s" %(u, p, t)
    return mt_opts

def get_rbac_opts():
    rbac_opts = ''

    cloud_admin_role = getattr(testbed, 'cloud_admin_role', None)
    if cloud_admin_role:
        rbac_opts = " --cloud_admin_role %s" % cloud_admin_role

    # if mt configured - ignore aaa-mode
    mt = getattr(testbed, 'multi_tenancy', None)
    aaa_mode = getattr(testbed, 'aaa_mode', None)

    if mt is not None:
        rbac_opts += " --aaa_mode %s" % ("cloud-admin" if mt else "no-auth")
    elif aaa_mode is not None:
        rbac_opts += " --aaa_mode %s" % aaa_mode
    return rbac_opts

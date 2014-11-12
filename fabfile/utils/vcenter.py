from fabfile.utils.host import get_from_testbed_dict

def get_vcenter_ip():
    return get_from_testbed_dict('vcenter', 'server', None)

def get_vcenter_port():
    return get_from_testbed_dict('vcenter', 'port', '443')

def get_vcenter_admin_user():
    return get_from_testbed_dict('vcenter', 'username', 'administrator@vsphere.local')

def get_vcenter_admin_password():
    return get_from_testbed_dict('vcenter', 'password', 'Contrail123!')

def get_vcenter_credentials():
    admin_user = get_vcenter_admin_user()
    admin_password = get_vcenter_admin_password()
    return admin_user, admin_password

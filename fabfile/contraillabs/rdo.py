"""Private contrail task for setting up RDO in the openstack node."""

from distutils.version import LooseVersion

from fabfile.config import *
from fabfile.utils.host import get_authserver_ip
from fabfile.utils.cluster import reboot_nodes
from fabfile.tasks.helpers import is_rpm_equal_or_higher

@task
@roles('openstack')
def fix_yum_repos():
    """ copy local repo locations """
    put('fabfile/contraillabs/repo/rhel70_rdo.repo', '/etc/yum.repos.d/cobbler-config.repo', use_sudo=True)
    sudo('yum clean all')


@task
@roles('openstack')
def install_rhosp5_repo():
    """ copy local rhosp5 repo locations """
    put('fabfile/contraillabs/repo/rhosp5_local.repo', '/etc/yum.repos.d/rhosp5_local.repo', use_sudo=True)
    sudo('yum clean all')

@task
@roles('openstack')
def install_rhosp7_repo():
    """ copy local rhosp7 repo locations """
    put('fabfile/contraillabs/repo/rhosp7_local.repo', '/etc/yum.repos.d/rhosp7_local.repo', use_sudo=True)
    sudo('yum clean all')

@task
@roles('openstack')
def install_rhosp6_repo():
    """ copy local rhosp6 repo locations """
    put('fabfile/contraillabs/repo/rhosp6_local.repo', '/etc/yum.repos.d/rhosp6_local.repo', use_sudo=True)
    sudo('yum clean all')

@task
@roles('openstack')
def install_rhosp8_repo():
    """ copy local rhosp8 repo locations """
    put('fabfile/contraillabs/repo/rhosp8_local.repo', '/etc/yum.repos.d/rhosp8_local.repo', use_sudo=True)
    sudo('yum clean all && yum clean expire-cache')

@task
@roles('all')
def update_all_node(reboot='True'):
    with settings(warn_only=True):
        sudo("yum -y install yum-utils")
        sudo("yum -y install kernel-headers-3.10.0-229.el7")
        sudo("yum update -y --exclude=kernel*")
        print "[%s]: Disable NeworkManager and reboot" % env.host_string
        sudo("systemctl stop NetworkManager")
        sudo("systemctl disable NetworkManager")
    if reboot == 'True':
        execute(reboot_nodes, env.host_string)
        pass
    else:
        print '[%s]: WARNING: Skipping Reboot as reboot!=True. '\
              'Reboot manually to avoid misconfiguration!' % env.host_string

@task
@roles('openstack')
def update_rhosp_node(reboot='True'):
    with settings(warn_only=True):
        sudo("yum -y install yum-utils")
        sudo("yum -y install kernel-headers")
        sudo("yum update -y")
        print "[%s]: Disable NeworkManager and reboot" % env.host_string
        sudo("systemctl stop NetworkManager")
        sudo("systemctl disable NetworkManager")
    if reboot == 'True':
        execute(reboot_nodes, env.host_string)
        pass
    else:
        print '[%s]: WARNING: Skipping Reboot as reboot!=True. '\
              'Reboot manually to avoid misconfiguration!' % env.host_string

@task
@roles('openstack')
def setup_rhosp_node():
    """Set up RHOSP Node"""
    mysql_passwd = 'juniper123'
    sudo('sudo yum install -y openstack-packstack')
    sudo('packstack --allinone \
                    --mariadb-pw=%s \
                    --use-epel=n \
                    --nagios-install=n \
                    --os-heat-install=y \
                    --os-heat-mysql-password=%s' % (mysql_passwd, mysql_passwd))
    openstack_password = getattr(env, 'openstack_admin_password', 'c0ntrail123')
    sudo('source keystonerc_admin && keystone user-password-update --pass %s admin' % openstack_password)
    sudo("sed -i -e 's/export OS_PASSWORD=.*/export OS_PASSWORD=%s/' keystonerc_admin " % openstack_password)

    # create mysql token file for use by contrail sanity scripts
    sudo("mkdir -p /etc/contrail/")
    sudo("echo %s > /etc/contrail/mysql.token" % mysql_passwd)

    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    sudo("service openstack-nova-compute stop")
    sudo("chkconfig openstack-nova-compute off")
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    sudo("service neutron-server stop")
    sudo("chkconfig neutron-server off")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    with settings(warn_only=True):
        openstackrc_file = sudo("ls /etc/contrail/openstackrc")
        if openstackrc_file.return_code != 0:
            sudo('mkdir -p /etc/contrail/')
            sudo("ln -s /root/keystonerc_admin /etc/contrail/openstackrc")

    cfgm_0_ip = testbed.env['roledefs']['cfgm'][0].split('@')[1]
    authserver_ip = get_authserver_ip()
    # For juno, neutron_url is deprecated instead use "url" in neutron section
    api_version = sudo("rpm -q --queryformat='%{VERSION}' openstack-nova-api")
    is_juno_or_higher = is_rpm_equal_or_higher("0 2014.2.2 2.el7ost")
    if is_juno_or_higher:
        sudo("openstack-config --set /etc/nova/nova.conf neutron url http://%s:9696" % cfgm_0_ip)
    else:
        sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_url http://%s:9696" % cfgm_0_ip)

    sudo("source /etc/contrail/openstackrc; nova service-disable $(hostname) nova-compute")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:35357/v2.0" % authserver_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  compute_driver nova.virt.libvirt.LibvirtDriver")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  novncproxy_port 5999")

    # remove endpoint lists pointing to openstack and recreate point to first cfgm
    os_ip = testbed.env['roledefs']['openstack'][0].split('@')[1]
    endpoint_id_openstack = sudo('source /etc/contrail/openstackrc; keystone endpoint-list 2> /dev/null | grep %s:9696 | tr -d " " | cut -d "|" -f2' % os_ip)
    # remove endpoint list
    sudo('source /etc/contrail/openstackrc; keystone endpoint-delete %s' % endpoint_id_openstack)
    with settings(warn_only=True):
        status = sudo('source /etc/contrail/openstackrc; keystone endpoint-list | grep %s' % endpoint_id_openstack)
        if status.succeeded:
            print "WARNING: Neutron Endpoint pointing to  openstack node is not removed"
            print "WARNING: Removing neutron endpoint pointing to openstack node from db"
            sudo('mysql -u root  -o keystone -e "delete from endpoint where url=\'http://%s:9696\'";' % os_ip)
        status = sudo('source /etc/contrail/openstackrc; keystone endpoint-list | grep %s' % endpoint_id_openstack)
        if status.succeeded:
            raise RuntimeError('Delete neutron endpoint pointing to openstack node from db failed')

    # recreate with cfgm
    endpoint_cfgm = 'http://%s:9696' % cfgm_0_ip

    # Workaround as CI is not setting env.keystone in testbed.py
    if testbed.env.get('keystone', None) is None:
        region_name = 'RegionOne'
    else:
        region_name = testbed.env['keystone']["region_name"]

    sudo('source /etc/contrail/openstackrc; \
          keystone endpoint-create --region %s \
                                   --service neutron \
                                   --publicurl %s \
                                   --adminurl %s \
                                   --internalurl %s' % (region_name, endpoint_cfgm, endpoint_cfgm, endpoint_cfgm))
    # display endpoint-list
    sudo('source /etc/contrail/openstackrc; keystone endpoint-list')
    sudo("service openstack-nova-api restart")
    sudo("service openstack-nova-conductor restart")
    sudo("service openstack-nova-scheduler restart")
    sudo("service openstack-nova-novncproxy restart")
    sudo("service openstack-nova-consoleauth restart")
    sudo("iptables --flush")
    sudo("sudo service iptables stop; echo pass")
    sudo("sudo service ip6tables stop; echo pass")
    sudo("sudo systemctl stop firewalld; echo pass")
    sudo("sudo systemctl status firewalld; echo pass")
    sudo("sudo chkconfig firewalld off; echo pass")
    sudo("sudo /usr/libexec/iptables/iptables.init stop; echo pass")
    sudo("sudo /usr/libexec/iptables/ip6tables.init stop; echo pass")
    sudo("sudo service iptables save; echo pass")
    sudo("sudo service ip6tables save; echo pass")
    sudo("mkdir -p /var/crashes")

    steps = "\n\n\n"
    steps += "="*160
    steps += "\nSteps to bring up contrail with the RHOSP:\n\
                1. Execute fab update_keystone_admin_token \n \
                2. Execute fab update_service_tenant \n \
                3. Execute fab update_neutron_password \n \
                4. Execute fab update_nova_password \n \
                5. Execute fab install_without_openstack \n\
                6. Execute fab setup_without_openstack\n"
    steps += "="*160
    print steps

@task
@roles('openstack')
def setup_rdo(rdo_url='https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm'):
    """Set up RDO in the openstack node"""
    with settings(warn_only=True):
         sudo('sudo yum -y install %s' % rdo_url)
    execute(fix_yum_repos)
    with settings(warn_only=True):
        sudo('sudo yum install -y openstack-packstack')
    sudo('packstack --allinone --mariadb-pw=juniper123 --use-epel=n --nagios-install=n')
    openstack_password = getattr(env, 'openstack_admin_password', 'contrail123')
    sudo('source keystonerc_admin && keystone user-password-update --pass %s admin' % openstack_password)
    sudo("sed -i -e 's/export OS_PASSWORD=.*/export OS_PASSWORD=%s/' keystonerc_admin " % openstack_password)
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    sudo("service openstack-nova-compute stop")
    with settings(warn_only=True):
        sudo("service openstack-nova-compute status")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    sudo("service neutron-server stop")
    with settings(warn_only=True):
        sudo("service neutron-server status")
    with settings(warn_only=True):
        openstackrc_file = sudo("ls /etc/contrail/openstackrc")
        if openstackrc_file.return_code != 0:
            sudo('mkdir -p /etc/contrail/')
            sudo("ln -s ~/keystonerc_admin /etc/contrail/openstackrc")
    cfgm_0_ip = testbed.env['roledefs']['cfgm'][0].split('@')[1]
    authserver_ip = get_authserver_ip()
    sudo("source /etc/contrail/openstackrc; nova service-disable $(hostname) nova-compute")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT network_api_class nova.network.neutronv2.api.API")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_url http://%s:9696" % cfgm_0_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT neutron_admin_auth_url http://%s:35357/v2.0" % authserver_ip)
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  compute_driver nova.virt.libvirt.LibvirtDriver")
    sudo("openstack-config --set /etc/nova/nova.conf DEFAULT  novncproxy_port 5999")
    sudo("service openstack-nova-api restart")
    sudo("service openstack-nova-conductor restart")
    sudo("service openstack-nova-scheduler restart")
    sudo("service openstack-nova-novncproxy restart")
    sudo("service openstack-nova-consoleauth restart")
    sudo("iptables --flush")
    sudo("sudo service iptables stop; echo pass")
    sudo("sudo service ip6tables stop; echo pass")
    sudo("sudo systemctl stop firewalld; echo pass")
    sudo("sudo systemctl status firewalld; echo pass")
    sudo("sudo chkconfig firewalld off; echo pass")
    sudo("sudo /usr/libexec/iptables/iptables.init stop; echo pass")
    sudo("sudo /usr/libexec/iptables/ip6tables.init stop; echo pass")
    sudo("sudo service iptables save; echo pass")
    sudo("sudo service ip6tables save; echo pass")

    steps = "\n\n\n"
    steps += "="*160
    steps += "\nSteps to bring up contrail with the RDO:\n\
                1. Get the admin_token from /etc/keystone/keystone.conf of the openstack node and populate it as service_token in the testbed.py.\n\
                2. fab install_without_openstack (This step can be executed even before fab setup_rdo)\n\
                3. fab setup_without_openstack\n"
    steps += "="*160
    print steps


@task
def update_service_tenant():
    '''Retrieve neutron service tenant name from RHOSP openstack node and
       update service_tenant in env.keystone section
    '''
    openstack_node = testbed.env['roledefs']['openstack'][0]
    with settings(host_string=openstack_node):
        neutron_tenant_id = sudo('source /etc/contrail/openstackrc; keystone user-get neutron 2> /dev/null | grep tenantId | tr -d " " | cut -d "|" -f3')
        if not neutron_tenant_id:
            raise RuntimeError('Unable to retrieve neutron tenant ID from openstack node (%s)' % openstack_node)
        neutron_service_name = sudo('source /etc/contrail/openstackrc; keystone tenant-list  2> /dev/null| grep %s | tr -d " " | cut -d "|" -f3' % neutron_tenant_id)
        print 'Retrieved Neutron service tenant name: %s' % neutron_service_name
        print 'Updating testbed.py with neutron service tenant name under env.keystone section'
        local('sed -i "s/\'service_tenant\'.*/\'service_tenant\' : \'%s\',/g" fabfile/testbeds/testbed.py' % neutron_service_name)

@task
def update_neutron_password(path='/root/packstack-answers-*.txt'):
    '''Retrieve neutron password from RHOSP openstack node packstack answers file and
       update neutron_password in env.keystone section
    '''
    openstack_node = testbed.env['roledefs']['openstack'][0]
    with settings(host_string=openstack_node):
        neutron_passwd = sudo('grep CONFIG_NEUTRON_KS_PW %s | grep -Po "CONFIG_NEUTRON_KS_PW=\K.*"' % path)
    if not neutron_passwd:
            raise RuntimeError('Unable to retrieve neutron password from openstack node (%s)' % openstack_node)
    local('sed -i "s/\'neutron_password\'.*/\'neutron_password\' : \'%s\',/g" fabfile/testbeds/testbed.py' % neutron_passwd)

@task
def update_nova_password(path='/root/packstack-answers-*.txt'):
    '''Retrieve nova password from RHOSP openstack node packstack answers file and
       update nova_password in env.keystone section
    '''
    openstack_node = testbed.env['roledefs']['openstack'][0]
    with settings(host_string=openstack_node):
        nova_passwd = sudo('grep CONFIG_NOVA_KS_PW %s | grep -Po "CONFIG_NOVA_KS_PW=\K.*"' % path)
    if not nova_passwd:
            raise RuntimeError('Unable to retrieve neutron password from openstack node (%s)' % openstack_node)
    local('sed -i "s/\'nova_password\'.*/\'nova_password\' : \'%s\',/g" fabfile/testbeds/testbed.py' % nova_passwd)

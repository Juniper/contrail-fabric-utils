from fabric.api import *
from fabric.context_managers import env
from distutils.version import LooseVersion

from fabfile.config import *
from fabfile.tasks.install import pkg_install
from fabfile.tasks.upgrade import upgrade_compute_node
from fabfile.utils.host import get_env_passwords, hstr_to_ip,\
              get_control_host_string, get_bgp_md5
from fabfile.utils.multitenancy import get_mt_opts
from fabfile.tasks.provision import prov_analytics_node
from fabfile.tasks.provision import prov_config_node
from fabfile.tasks.provision import prov_database_node
from fabfile.tasks.provision import prov_control_bgp_node
from fabfile.utils.install import get_vrouter_kmod_pkg
from fabfile.utils.host import *
from fabfile.utils.fabos import *
from fabric.contrib.files import exists


@task
@roles('compute')
def issu_contrail_switch_compute(discovery_ip):
    """Migrate the contrail compute nodes to new discovery."""
    execute("issu_contrail_switch_compute_node", discovery_ip, env.host_string)

@task
def issu_contrail_switch_compute_node(discovery_ip, *args):
    """Usage: fab issu_contrail_switch_compute_node:<new_discovery_ip>,root@1.1.1.4..."""
    for host in args:
        with settings(host_string=host):
            sudo("route -n")
            sudo("openstack-config --set /etc/contrail/contrail-vrouter-agent.conf DISCOVERY server %s" %(discovery_ip))
            sudo("openstack-config --set /etc/contrail/supervisord_vrouter_files/contrail-vrouter-agent.ini program:contrail-vrouter-agent autostart true")
            sudo("openstack-config --set /etc/contrail/supervisord_vrouter_files/contrail-vrouter-agent.ini program:contrail-vrouter-agent killasgroup true")
            sudo("openstack-config --set /etc/contrail/contrail-vrouter-nodemgr.conf DISCOVERY server %s" %(discovery_ip))
            sudo("service supervisor-vrouter restart")
            sudo("contrail-status")
            sudo("route -n")

@task
@roles('compute')
def issu_contrail_prepare_compute():
    """Prepare compute nodes for upgrade"""
    execute("issu_contrail_prepare_compute_node", env.host_string)

@task
def issu_contrail_prepare_compute_node(*args):
    """Usage: fab issu_contrail_prepare_compute_node:root@1.1.1.4..."""
    for host in args:
        with settings(host_string=host):
            sudo('route -n')
            sudo("openstack-config --del /etc/contrail/supervisord_vrouter_files/contrail-vrouter-agent.ini program:contrail-vrouter-agent autostart")
            sudo("openstack-config --del /etc/contrail/supervisord_vrouter_files/contrail-vrouter-agent.ini program:contrail-vrouter-agent killasgroup")
            sudo("contrail-status")

@task
@roles('compute')
def issu_contrail_upgrade_compute(from_rel, pkg):
    """Upgrade compute node"""
    execute("issu_contrail_upgrade_compute_node", from_rel, pkg, env.host_string)

@task
def issu_contrail_upgrade_compute_node(from_rel, pkg, *args):
    """Usage: fab issu_conntrail_compute_upgrade:from_rel,pkg,root@1.1.1.4"""
    for host in args:
        with settings(host_string=host):
            sudo('contrail-version')
            execute("upgrade_compute_node", from_rel, pkg, host, manage_nova_compute='no', configure_nova='no')
            sudo('contrail-version')

@task
@roles('cfgm')
def issu_contrail_prepare_new_control():
    """Prepare new control node for ISSU upgrade"""
    execute("issu_contrail_prepare_new_control_node", env.host_string)

@task
def issu_contrail_prepare_new_control_node(*args):
    """Usage: fab issu_contrail_control_prepare_new:root@1.1.1.4 """
    for host in args:
        with settings(host_string=host):
            sudo('contrail-status')
            sudo("openstack-config --set /etc/contrail/supervisord_config.conf include files \"/etc/contrail/supervisord_config_files/contrail-api.ini  /etc/contrail/supervisord_config_files/contrail-discovery.ini /etc/contrail/supervisord_config_files/ifmap.ini\"")
            sudo("contrail-status")
            sudo("service supervisor-config restart")
            sudo("contrail-status")
            sudo("service supervisor-config stop")
            sudo("contrail-status")

@task
@roles('cfgm')
def issu_contrail_post_new_control():
    """Post operations on new control node"""
    execute("issu_contrail_post_new_control_node", env.host_string)

@task
def issu_contrail_post_new_control_node(*args):
    """Usage: fab issu_contrail_control_post_new:root@1.1.1.4"""
    for host in args:
        with settings(host_string=host):
            sudo('contrail-status')
            sudo("openstack-config --set /etc/contrail/supervisord_config.conf include files \"/etc/contrail/supervisord_config_files/*.ini\"")
            sudo("service supervisor-config restart")
            sudo("contrail-status")

@task
@roles('control')
def issu_contrail_peer_controls_old_with_new():
    execute('issu_contrail_config_new_control_on_old', env.host_string)

@task
def issu_contrail_config_new_control_on_old(*args):
    """Usage: fab issu_contrail_config_new_control_on_ol:root@1.1.1.4"""
    #sudo("python /opt/contrail/utils/provision_control.py --host_name issu-vm15 --host_ip 10.87.64.67 --api_server_ip 10.87.64.57 --api_server_port 9100 --oper add --admin_user admin --admin_password secret123 --admin_tenant_name admin --router_asn 64512 --ibgp_auto_mesh")
    cfgm_host = env.roledefs['oldcfgm'][0]
    for host_string in args:
        execute('prov_control_bgp_node', host_string, cfgm_host=cfgm_host)

@task
@roles('oldcfgm')
def issu_prune_old_config():
    execute('issu_prune_old_config_node', env.host_string)

@task
@roles('cfgm')
def issu_prune_old_config_node(*args):
    for host_string in args:
         execute('prov_config_node', host_string, oper='del')

@task
@roles('oldcollector')
def issu_prune_old_collector():
    execute('issu_prune_old_collector_node', env.host_string)

@task
@roles('collector')
def issu_prune_old_collector_node(*args):
    for host_string in args:
        execute('prov_analytics_node', host_string, oper='del')

@task
@roles('oldcontrol')
def issu_prune_old_control():
    execute('issu_prune_old_control_node', env.host_string)

@task
@roles('control')
def issu_prune_old_control_node(*args):
    for host_string in args:
        execute('prov_control_bgp_node', host_string, oper='del')

@task
@roles('olddatabase')
def issu_prune_old_database():
    execute('issu_prune_old_database_node', env.host_string)

@task
@roles('database')
def issu_prune_old_database_node(*args):
    for host_string in args:
        execute('prov_database_node', host_string, oper='del')

@task
def issu_prov_config():
    execute('prov_config')

@task
def issu_prov_collector():
    execute('prov_analytics')

@task
def issu_prov_database():
    execute('prov_database')

@task
def issu_contrail_finalize_config_node():
    execute('issu_prune_old_config')
    execute('issu_prune_old_collector')
    execute('issu_prune_old_control')
    execute('issu_prune_old_database')
    execute('issu_prov_config')
    execute('issu_prov_collector')
    execute('issu_prov_database')

@task
@roles('build')
def issu_contrail_stop_old_node():
    execute("issu_contrail_stop_old_cfgm")
    execute("issu_contrail_stop_old_control")
    execute("issu_contrail_stop_old_webui")
    execute("issu_contrail_stop_old_collector")

@task
@roles('oldcfgm')
def issu_contrail_stop_old_cfgm():
    for host in env.roledefs['oldcfgm']:
        sudo("contrail-status")
        execute("stop_cfgm_node", host)
        sudo("contrail-status")

@task
@roles('oldcontrol')
def issu_contrail_stop_old_control():
    for host in env.roledefs['oldcontrol']:
        sudo("contrail-status")
        execute("stop_control_node", host)
        sudo("contrail-status")

@task
@roles('oldwebui')
def issu_contrail_stop_old_webui():
    for host in env.roledefs['oldcontrol']:
        sudo("contrail-status")
        execute("stop_webui_node", host)
        sudo("contrail-status")

@task
@roles('oldcollector')
def issu_contrail_stop_old_collector():
    for host in env.roledefs['oldcontrol']:
        sudo("contrail-status")
        execute("stop_collector_node", host)
        sudo("contrail-status")

@task
@roles('openstack')
def issu_contrail_migrate_nb(oldip, newip):
    execute('issu_contrail_migrate_nb_connectivity', oldip, newip, env.host_string)
@task
def issu_contrail_migrate_nb_connectivity(oldip, newip, *args):
    """ Usage: fab issu_contrail_migrate_nd:oldip,newip,root@1.1.1.4"""
    for host in args:
        with settings(host_string=host):
            sudo("sed -i 's/%s/%s/g' /etc/haproxy/haproxy.cfg" %(oldip, newip))
            sudo("service haproxy restart")

@task
@roles('openstack')
def issu_freeze_nb():
    execute('issu_freeze_nb_connectivity', env.host_string)

@task
def issu_freeze_nb_connectivity(*args):
    """Usage: fab issu_freeze_nb_connectivity:root@1.1.1.4"""
    for host in args:
        with settings(host_string=host):
            sudo("service haproxy stop")

@task
@roles('openstack')
def issu_open_nb():
    execute('issu_open_nb_connectivity', env.host_string)

@task
def issu_open_nb_connectivity(*args):
    """Usage: fab issu_open_nb_connectivity:root@1.1.1.4"""
    for host in args:
        with settings(host_string=host):
            sudo('contrail-status')
            sudo("service haproxy start")

@task
def issu_pre_sync():
    sudo("contrail-issu-pre-sync")

@task
def issu_run_sync():
    sudo("touch /etc/supervisor/conf.d/contrail-issu.conf")
    cmd = "openstack-config --set /etc/supervisor/conf.d/contrail-issu.conf program:contrail-issu"
    sudo("%s command 'contrail-issu-run-sync'" %(cmd))
    sudo("%s numprocs 1" %(cmd))
    sudo("openstack-config --set /etc/supervisor/conf.d/contrail-issu.conf program:contrail-issu process_name '%(process_num)s'")
    sudo("%s redirect_stderr true" %(cmd))
    sudo("openstack-config --set /etc/supervisor/conf.d/contrail-issu.conf program:contrail-issu stdout_logfile  '/var/log/issu-contrail-run-sync-%(process_num)s-stdout.log'")
    sudo("openstack-config --set /etc/supervisor/conf.d/contrail-issu.conf program:contrail-issu stderr_logfile '/dev/null'") 
    sudo("%s priority 440" %(cmd))
    sudo("%s autostart true" %(cmd))
    sudo("%s killasgroup false" %(cmd))
    sudo("%s stopsignal KILL" %(cmd))
    sudo("%s exitcodes 0" %(cmd))
    sudo("service supervisor restart")

@task
def issu_post_sync():
    sudo("rm -f /etc/supervisor/conf.d/contrail-issu.conf")
    sudo("service supervisor restart")
    sudo("contrail-issu-post-sync")
    sudo("contrail-issu-zk-sync")
 
@task
@roles('build')
def issu_contrail_migrate_config():
    execute('issu_contrail_peer_controls_old_with_new')
    execute('issu_contrail_prepare_new_control')
    execute('issu_freeze_nb')
    execute('issu_pre_sync')
    execute('issu_run_sync')
    execute('issu_open_nb')

@task
@roles('compute')
def issu_contrail_migrate_compute(from_rel, pkg, new_discovery):
    execute('issu_contrail_migrate_compute_node', from_rel, pkg, new_discovery, env.host_string)

@task
def issu_contrail_migrate_compute_node(from_rel, pkg, new_discovery, *args):
    """Usage: fab issu_contrail_migrate_compute_node:from_rel,pkg,new_discovery,root@1.1.1.4"""
    #new discovery can be extracted from testbed.py
    print "Initiating compute migration"
    for host_string in args:
        with settings(host_string=host_string):
            execute('issu_contrail_prepare_compute_node', host_string)
            execute('issu_contrail_upgrade_compute_node', from_rel, pkg, host_string)
            execute('issu_contrail_switch_compute_node', new_discovery, host_string)
    print "Compute migration done"

@task
@roles('compute')
def issu_contrail_downgrade_compute(from_rel, pkg, discovery_ip):
    execute("issu_contrail_downgrade_compute_node", from_rel, pkg, env.host_string)

@task
def issu_contrail_downgrade_compute_node(from_rel, pkg, *args):
    #Downgrade is a reference till role based packaginig is done.
    """Usage: fab issu_conntrail_compute_upgrade:from_rel,pkg,root@1.1.1.4"""
    remove_pkgs = 'contrail-setup %s contrail-fabric-utils contrail-install-packages contrail-lib contrail-nodemgr contrail-setup contrail-utils contrail-vrouter-utils python-contrail contrail-openstack-vrouter  contrail-nova-vif contrail-setup contrail-vrouter-utils' %(get_vrouter_kmod_pkg())
    for host in args:
        with settings(host_string=host):
            if sudo('lsb_release -i | grep Ubuntu | wc -l'):
                sudo('DEBIAN_FRONTEND=noninteractive apt-get -y remove %s' %(remove_pkgs))
            else:
                sudo('yum remove -y %s' %(remove_pkgs))
            execute("upgrade_compute_node", from_rel, pkg, host, manage_nova_compute='no', configure_nova='no')
            sudo('contrail-version')

@task
@roles('compute')
def issu_contrail_rollback_compute(from_rel, pkg, discovery_ip):
    execute('issu_contrail_rollback_compute_node', from_rel, pkg, discovery_ip, env.host_string)

@task
def issu_contrail_rollback_compute_node(from_rel, pkg, discovery_ip, *args):
    """Usage: fab issu_contrail_rollback_compute_node:from_rel,pkg,discovery_ip,root@1.1.1.4"""
    print "Initiating compute rollback"
    for host_string in args:
        with settings(host_string=host_string):
            execute('issu_contrail_prepare_compute_node', host_string)
            execute('issu_contrail_downgrade_compute_node', from_rel, pkg, host_string)
            execute('issu_contrail_switch_compute_node', discovery_ip, host_string)
    print "Compute rollback done"

@task
@roles('build')
def issu_contrail_finalize(oldip, newip):
    #Oldip newip probably can be extracted from testbed.py
    execute('issu_contrail_stop_old_node')
    execute('issu_post_sync')
    execute('issu_contrail_post_new_control')
    execute('issu_contrail_migrate_nb', oldip, newip)
    execute('issu_contrail_finalize_config_node')

@task
def issu_contrail():
    #Currently not supported, will be supported once sync is a service
    #execute('issu_contrail_migrate_config')
    #execute('issu_contrail_migrate_compute')
    #execute('issu_contrail_finalize')
    print "Single touch ISSU is not yet supported"

#################################################################################################################
#
#
# ISSU Openstack JUNO to KILO and KILO to LIBERTY.
#
#
#################################################################################################################
@task
@roles('cfgm')
def issu_openstack_migrate_neutron(from_version, to_version):
    """Migrate neutron to new version of openstack"""
    execute("issu_openstack_migrate_neutron_node", from_version, to_version, env.host_string)

@task
def issu_openstack_migrate_neutron_node(from_version, to_version, *args):
    auth_host = get_authserver_ip()
    auth_port = get_authserver_port()
    admin_token = get_keystone_admin_token()
    for host_string in args:
        with settings(host_string=host_string):
            sudo("openstack-config --set /etc/contrail/vnc_api_lib.ini auth AUTHN_SERVER %s" %(auth_host))
            sudo("openstack-config --set /etc/contrail/contrail-keystone-auth.conf KEYSTONE auth_host %s" %(auth_host))
            sudo("openstack-config --set /etc/neutron/plugins/opencontrail/ContrailPlugin.ini KEYSTONE auth_url http://%s:%s/v2.0" %(auth_host, auth_port))
            cmd = "openstack-config --set /etc/neutron/neutron.conf keystone_authtoken"
            sudo("%s auth_host %s" %(cmd, auth_host))
            sudo("%s auth_uri http://%s:%s/v2.0/" %(cmd, auth_host, auth_port))
            sudo("%s identity_uri http://%s:5000" %(cmd, auth_host))
            sudo("%s admin_token %s" %(cmd, admin_token))
            if from_version == 'juno' and to_version == 'kilo':
                sudo("openstack-config --set /etc/neutron/neutron.conf upgrade_levels compute juno")
            elif from_version == 'kilo' and to_version == 'liberty':
                sudo("openstack-config --set /etc/neutron/neutron.conf upgrade_levels compute kilo")
            else:
                raise RuntimeError("Upgrade from %s to %s not supported" %(from_version, to_version))

            sudo("service neutron-server restart")
            sudo("service supervisor-config restart")
@task
@roles('cfgm')
def issu_openstack_upgrade_neutron(from_version, to_version, pkg):
    """Upgrade neutron packages in config node"""
    execute("issu_openstack_upgrade_neutron_node", from_version, to_version, pkg, env.host_string)

@task
def issu_openstack_upgrade_neutron_node(from_version, to_version, pkg, *args):
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string, is_openstack_upgrade='True')
            ostype = detect_ostype()
            if (ostype in ['ubuntu']):
                cmd = 'apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confold"'
            elif ostype in ['centos', 'fedora', 'redhat', 'centoslinux']:
                cmd = 'yum -y'
            else:
                raise RuntimeError("Unsupported OS")
            if from_version == 'juno' and to_version == 'kilo':
                sudo("%s install neutron-server" %(cmd))
            elif from_version == 'kilo' and to_version == 'liberty':
                sudo("%s install neutron-plugin-ml2 python-sqlalchemy-ext  python-alembic  python-oslo.utils neutron-server" %(cmd))
            else:
                raise RuntimeError("Upgrade from %s to %s not supported" %(from_version, to_version))

            sudo("%s install neutron-plugin-ml2 python-sqlalchemy-ext  python-alembic  python-oslo.utils neutron-server" %(cmd))
            sudo("%s install python-neutron-lbaas" %(cmd))
            execute('issu_provision_neutron_node', from_version, to_version, host_string)

@task
def issu_provision_neutron_node(from_version, to_version, *args):
    for host_string in args:
        val = sudo('openstack-config --get /etc/neutron/neutron.conf DEFAULT lock_path')
        sudo("openstack-config --set /etc/neutron/neutron.conf oslo_concurrency lock_path %s" %(val))
        if from_version == 'kilo' and to_version == 'liberty':
            PYDIST=sudo('python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"')
            sudo('openstack-config --set /etc/neutron/neutron.conf DEFAULT service_plugins neutron_plugin_contrail.plugins.opencontrail.loadbalancer.v2.plugin.LoadBalancerPluginV2')
            sudo('openstack-config --set /etc/neutron/neutron.conf DEFAULT api_extensions_path extensions:%s/neutron_plugin_contrail/extensions:%s/neutron_lbaas/extensions' %(PYDIST, PYDIST))
        sudo("service neutron-server restart")
        sudo("service supervisor-config restart")

@task
@roles('compute')
def issu_openstack_migrate_compute(from_version, to_version):
    """Migrate compute node to new version of openstack"""
    execute("issu_openstack_migrate_compute_node", from_version, to_version, env.host_string)

@task
def issu_openstack_migrate_compute_node(from_version, to_version, *args):
    auth_host = get_authserver_ip()
    auth_port = get_authserver_port()
    rabbit_hosts = ','.join([amqp_server + ':' + get_openstack_amqp_port()
        for amqp_server in get_openstack_amqp_servers()])
    openstack_host = env.roledefs['openstack'][0]
    for host_string in args:
        with settings(host_string=host_string):
            sudo("openstack-config --set /etc/nova/nova.conf DEFAULT rabbit_hosts %s" %(rabbit_hosts))
            if from_version == 'juno' and to_version == 'kilo':
                cmd = "openstack-config --set /etc/nova/nova.conf"
                sudo("%s DEFAULT neutron_admin_auth_url http://%s:%s/v2.0/" % (cmd, auth_host, auth_port))
                sudo("%s DEFAULT glance_host %s" %(cmd, openstack_host))
                sudo("%s DEFAULT novncproxy_base_url http://%s/:5999/vnc_auto.html" %(cmd, openstack_host))
                sudo("%s keystone_authtoken auth_host %s" %(cmd, auth_host))
                sudo("%s upgrade_levels compute juno" %(cmd))
            elif from_version == 'kilo' and to_version == 'liberty':
                cmd = "openstack-config --set /etc/nova/nova.conf"
                sudo("%s neutron admin_auth_url http://%s:%s/v2.0/" %(cmd, auth_host, auth_port))
                sudo("%s glance host root@%s" %(cmd, openstack_host))
                sudo("%s keystone_authtoken auth_host %s" %(cmd, auth_host))
                sudo("%s upgrade_levels compute kilo" %(cmd))
            else:
                raise RuntimeError("Upgrade from %s to %s not supported" %(from_version, to_version))
            sudo("service nova-compute restart")
@task
@roles('compute')
def issu_openstack_upgrade_compute(from_version, to_version, pkg):
    """Upgrade nova packages in compute node"""
    execute("issu_openstack_upgrade_compute_node", from_version, to_version, pkg, env.host_string)

@task
def issu_openstack_upgrade_compute_node(from_version, to_version, pkg, *args):
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string, is_openstack_upgrade='True')
            ostype = detect_ostype()
            if (ostype in ['ubuntu']):
                cmd = 'apt-get -y --force-yes -o Dpkg::Options::="--force-overwrite" -o Dpkg::Options::="--force-confold"'
            elif ostype in ['centos', 'fedora', 'redhat', 'centoslinux']:
                cmd = 'yum -y'
            else:
                raise RuntimeError("Unsupported OS")
                print "Invalid OS"
                return
            sudo("%s install python-neutronclient" %(cmd))
            sudo("%s install python-nova" %(cmd))
            sudo("%s install python-novaclient" %(cmd))
            sudo("%s install nova-compute-libvirt" %(cmd))
            if from_version == 'juno' and to_version == 'kilo':
                execute('provision_compute_node', host_string)
@task
def provision_compute_node(*args):
    admin_user, admin_password = get_authserver_credentials()
    admin_tenant_name = get_admin_tenant_name()
    auth_host = get_authserver_ip()
    auth_port = get_authserver_port()
    auth_protocol = get_authserver_protocol()
    signing_dir = "/tmp/keystone-signing-nova"
    for host_string in args:
        with settings(host_string=host_string):
            cmd_get = "openstack-config --get /etc/nova/nova.conf DEFAULT"
            cmd_set = "openstack-config --set /etc/nova/nova.conf"
            val = sudo("%s compute_driver" %(cmd_get))
            sudo("%s compute compute_driver %s" %(cmd_set, val))
            val = sudo("%s neutron_admin_auth_url" %(cmd_get))
            sudo("%s neutron admin_auth_url %s" %(cmd_set, val))
            val = sudo("%s neutron_admin_username" %(cmd_get))
            sudo("%s neutron admin_username %s" %(cmd_set, val))
            val = sudo("%s neutron_admin_password" %(cmd_get))
            sudo("%s neutron admin_password %s" %(cmd_set, val))
            val = sudo("%s neutron_admin_tenant_name" %(cmd_get))
            sudo("%s neutron admin_tenant_name %s" %(cmd_set, val))
            val = sudo("%s neutron_url" %(cmd_get))
            sudo("%s neutron url %s" %(cmd_set, val))
            val = sudo("%s neutron_url_timeout" %(cmd_get))
            sudo("%s neutron url_timeout %s" %(cmd_set, val))
            val = sudo("%s glance_host" %(cmd_get))
            sudo("%s glance host %s" %(cmd_set, val))
            sudo("%s keystone_authtoken admin_tenant_name %s" %(cmd_set, admin_tenant_name))
            sudo("%s keystone_authtoken admin_user %s" %(cmd_set, admin_user))
            sudo("%s keystone_authtoken admin_password %s" %(cmd_set, admin_password))
            sudo("%s keystone_authtoken auth_host %s" %(cmd_set, auth_host))
            sudo("%s keystone_authtoken auth_protocol %s" %(cmd_set, auth_protocol))
            sudo("%s keystone_authtoken auth_port %s" %(cmd_set, auth_port))
            sudo("%s keystone_authtoken signing_dir %s" %(cmd_set, signing_dir))
            sudo("service nova-compute restart")

@task
def issu_openstack_finalize_upgrade():
    execute('issu_openstack_finalize_compute')
    execute('issu_openstack_finalize_neutron')
    execute('issu_openstack_finalize_openstack')

@task
@roles('compute')
def issu_openstack_finalize_compute():
    execute('issu_openstack_finalize_compute_node', env.host_string)
@task
def issu_openstack_finalize_compute_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo('openstack-config --del /etc/nova/nova.conf upgrade_levels')
            sudo('service nova-compute restart')

@task
@roles('cfgm')
def issu_openstack_finalize_neutron():
    execute('issu_openstack_finalize_neutron_node', env.host_string)

@task
def issu_openstack_finalize_neutron_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo('openstack-config --del /etc/neutron/neutron.conf upgrade_levels')
            sudo('service neutron-server restart')

@task
@roles('openstack')
def issu_openstack_finalize_openstack():
    execute('issu_openstack_finalize_openstack_node', env.host_string)

@task
def issu_openstack_finalize_openstack_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo('openstack-config --del /etc/nova/nova.conf upgrade_levels')
            sudo('sync; reboot --force')

@task
@roles('build')
def issu_openstack_migrate_to_new_controller(from_version, to_version):
    db_file = 'issu_openstack_db'
    execute('issu_openstack_snapshot_db', from_version, to_version, db_file)
    execute('issu_openstack_sync', from_version, to_version, db_file)
    execute('issu_openstack_migrate_neutron', from_version, to_version)
    execute('issu_openstack_migrate_compute', from_version, to_version)
    execute('issu_openstack_reboot_openstack')

@task
@roles('openstack')
def issu_openstack_reboot_openstack():
    execute('issu_openstack_reboot_openstack_node', env.host_string)
@task
def issu_openstack_reboot_openstack_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo('sync; reboot --force')
@task
@roles('openstack')
def issu_openstack_sync(from_version, to_version, db_file):
    sql_passwd = sudo('cat /etc/contrail/mysql.token')
    newopenstack=host_string_to_ip(env.host_string)
    oldopenstack=host_string_to_ip(env.roledefs['oldopenstack'][0])
    sudo("sed -i 's/%s/%s/g' %s" %(oldopenstack, newopenstack, db_file))
    if from_version == 'kilo' and to_version == 'liberty':
        from_string = "$(compute_port)s"
        to_string = "8774"
        sudo("sed -i 's/%s/%s/g' %s" %(from_string, to_string, db_file))
    print sql_passwd
    sudo("mysql --user root --password=%s < %s" %(sql_passwd, db_file))
    sudo("nova-manage db sync")
    sudo("keystone-manage db_sync")
    sudo("cinder-manage db sync")
    sudo("glance-manage db sync")
    if from_version == 'juno' and to_version == 'kilo':
        sudo("openstack-config --set /etc/nova/nova.conf upgrade_levels compute juno")
    elif from_version == 'kilo' and to_version == 'liberty':
        sudo("openstack-config --set /etc/nova/nova.conf upgrade_levels compute kilo")
    else:
        raise RuntimeError("Upgrade from %s to %s not supported" %(from_version, to_version))

    print "Migrate openstack orchestrator"

@task
@roles('oldopenstack')
def issu_openstack_snapshot_db(from_version, to_version, db_file):
    if from_version == 'kilo' and to_version == 'liberty':
        sudo("nova-manage db migrate_flavor_data")
    sql_passwd = sudo('cat /etc/contrail/mysql.token')
    sudo("mysqldump -u root  --password=%s --opt --add-drop-database --all-databases > %s" %(sql_passwd, db_file))
    svc_token = '/etc/contrail/service.token'
    mysql_token = '/etc/contrail/mysql.token'
    get_as_sudo('~/%s' %db_file, '/tmp')
    get_as_sudo(svc_token, '/tmp')
    get_as_sudo(mysql_token, '/tmp')
    with settings(host_string=env.roledefs['openstack'][0], password=get_env_passwords(env.roledefs['openstack'][0])):
        put('/tmp/%s' %(db_file), '~/', use_sudo=True)
        put('/tmp/service.token', svc_token, use_sudo=True)
        put('/tmp/mysql.token', mysql_token, use_sudo=True)

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

ISSU_DIR = '/usr/share/contrail-utils'
#ISSU_DIR = '~/'

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
    #This will become a service later on
    sudo("python %s/issu_contrail_pre_sync.py" %(ISSU_DIR))

@task
def issu_run_sync():
    #This will become a service later on
    sudo("python %s/issu_contrail_run_sync.py" %(ISSU_DIR))

@task
def issu_post_sync():
    #This will become a service later on
    sudo("python %s/issu_contrail_post_sync.py" %(ISSU_DIR))
    sudo("python %s/issu_contrail_zk_sync.py" %(ISSU_DIR))

@task
@roles('build')
def issu_contrail_migrate_config():
    execute('issu_contrail_peer_controls_old_with_new')
    execute('issu_contrail_prepare_new_control')
    execute('issu_freeze_nb')
    execute('issu_pre_sync')
    execute('issu_open_nb')
    #run_sync is a daemon,so order changed.But there is a race condition
    execute('issu_run_sync')

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

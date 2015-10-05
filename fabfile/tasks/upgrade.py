from fabfile.config import *

from fabfile.tasks.install import pkg_install
from fabfile.tasks.provision import fixup_restart_haproxy_in_all_cfgm
from fabfile.utils.cluster import get_toragent_nodes, get_tsn_nodes
from fabfile.utils.commandline import *
from fabfile.utils.fabos import get_release, detect_ostype, get_linux_distro
from fabfile.utils.install import get_compute_pkgs, get_openstack_pkgs
from fabfile.tasks.vmware import provision_vcenter_features

@task
@EXECUTE_TASK
@roles('openstack')
def upgrade_openstack(from_rel, pkg):
    """Upgrades the contrail openstack pkgs in all nodes defined in openstack."""
    execute("upgrade_openstack_node", from_rel, pkg, env.host_string)

@task
def upgrade_openstack_node(from_rel, pkg, *args):
    """Upgrades openstack pkgs in one or list of nodes. USAGE:fab upgrade_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_openstack_cmd(host_string, 'upgrade-vnc-openstack')
            cmd += ' -P %s' % ' '.join(get_openstack_pkgs())
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('database')
def upgrade_database(from_rel, pkg):
    """Upgrades the contrail database pkgs in all nodes defined in database."""
    execute("upgrade_database_node", from_rel, pkg, env.host_string)

@task
def upgrade_database_node(from_rel, pkg, *args):
    """Upgrades database pkgs in one or list of nodes. USAGE:fab upgrade_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_database_cmd(host_string, 'upgrade-vnc-database')
            cmd += ' -P contrail-openstack-database'
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('cfgm')
def upgrade_config(from_rel, pkg):
    """Upgrades the contrail config pkgs in all nodes defined in config."""
    execute("upgrade_config_node", from_rel, pkg, env.host_string)

@task
def upgrade_config_node(from_rel, pkg, *args):
    """Upgrades config pkgs in one or list of nodes. USAGE:fab upgrade_config_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])

            #Downgrading keepalived as we are packaging lower version of keepalivd in R2.20
            if (float(from_rel) == 2.2 and get_release() >= 2.2):
                dist, version, extra = get_linux_distro()
                if version == '14.04':
                    cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes'
                    cmd += ' -o Dpkg::Options::="--force-overwrite"'
                    cmd += ' -o Dpkg::Options::="--force-confold" install keepalived=1.2.13-0~276~ubuntu14.04.1'
                    sudo(cmd)

            cmd = frame_vnc_config_cmd(host_string, 'upgrade-vnc-config')
            cmd += ' -P contrail-openstack-config'
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('collector')
def upgrade_collector(from_rel, pkg):
    """Upgrades the contrail collector pkgs in all nodes defined in collector."""
    execute("upgrade_collector_node", from_rel, pkg, env.host_string)

@task
def upgrade_collector_node(from_rel, pkg, *args):
    """Upgrades collector pkgs in one or list of nodes. USAGE:fab upgrade_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_collector_cmd(host_string, 'upgrade-vnc-collector')
            cmd += ' -P contrail-openstack-analytics'
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('control')
def upgrade_control(from_rel, pkg):
    """Upgrades the contrail control pkgs in all nodes defined in control."""
    execute("upgrade_control_node", from_rel, pkg, env.host_string)

@task
def upgrade_control_node(from_rel, pkg, *args):
    """Upgrades control pkgs in one or list of nodes. USAGE:fab upgrade_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_control_cmd(host_string, 'upgrade-vnc-control')
            cmd += ' -P contrail-openstack-control'
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('webui')
def upgrade_webui(from_rel, pkg):
    """Upgrades the contrail webui pkgs in all nodes defined in webui."""
    execute("upgrade_webui_node", from_rel, pkg, env.host_string)

@task
def upgrade_webui_node(from_rel, pkg, *args):
    """Upgrades webui pkgs in one or list of nodes. USAGE:fab upgrade_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_webui_cmd(host_string, 'upgrade-vnc-webui')
            cmd += ' -P contrail-openstack-webui'
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            sudo(cmd)

@task
@EXECUTE_TASK
@roles('compute')
def upgrade_compute(from_rel, pkg):
    """Upgrades the contrail compute pkgs in all nodes defined in compute."""
    execute("upgrade_compute_node", from_rel, pkg, env.host_string)

@task
def upgrade_compute_node(from_rel, pkg, *args):
    """Upgrades compute pkgs in one or list of nodes. USAGE:fab upgrade_compute_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with settings(host_string=host_string):
            execute('install_pkg_node', pkg, host_string)
            execute('create_install_repo_node', host_string)
            pkg_install(['contrail-setup'])
            cmd = frame_vnc_compute_cmd(host_string, 'upgrade-vnc-compute')

            manage_nova_compute='yes'
            if (env.host_string in get_tsn_nodes() or
                get_orchestrator() == 'vcenter'):
                manage_nova_compute='no'

            # Identify packages to upgrade
            pkgs = get_compute_pkgs(manage_nova_compute=manage_nova_compute)
            if (getattr(env, 'interface_rename', True) and
                detect_ostype() not in ['ubuntu', 'redhat']):
               pkgs.append('contrail-interface-name')
            if float(from_rel) < 2.1:
                dist, version, extra = get_linux_distro()
                if version == '14.04' and 'contrail-vrouter-3.13.0-35-generic' in pkgs:
                    pkgs.remove('contrail-vrouter-3.13.0-35-generic')
                    pkgs.append('contrail-vrouter-3.13.0-40-generic')
            # Identify roles of this node.
            roles = ['compute']
            if env.host_string in get_tsn_nodes():
                roles.append('tsn')
            if env.host_string in get_toragent_nodes():
                roles.append('toragent')

            cmd += ' -P %s' % ' '.join(pkgs)
            cmd += ' -F %s' % from_rel
            cmd += ' -T %s' % get_release()
            cmd += ' -R %s' % ' '.join(roles)
            sudo(cmd)

@roles('build')
@task
def upgrade_orchestrator(from_rel, pkg):
    if get_orchestrator() is 'openstack':
        execute('upgrade_openstack', from_rel, pkg)
        execute('setup_cmon_schema')
        execute('setup_cluster_monitors')
        execute('setup_cmon_param_zkonupgrade')
    if get_orchestrator() is 'vcenter':
        execute('upgrade_vcenter')

@roles('build')
@task
def upgrade_vcenter():
    apt_install(['contrail-vmware-utils'])
    vcenter_info = getattr(env, 'vcenter', None)
    if not vcenter_info:
        print 'Info: vcenter block is not defined in testbed file.Exiting'
        return
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return
    host_list = esxi_info.keys()
    provision_vcenter_features(vcenter_info, esxi_info, host_list)

@task
@roles('build')
def upgrade_contrail(from_rel, pkg, orch='yes'):
    """Upgrades all the contrail pkgs in all nodes.
    """
    execute('pre_check')
    execute('install_pkg_all', pkg)
    execute('stop_cfgm')
    execute('stop_rabbitmq')
    execute('stop_collector')
    if orch == 'yes':
        execute('upgrade_orchestrator', from_rel, pkg)
    execute('upgrade_database', from_rel, pkg)
    execute('upgrade_config', from_rel, pkg)
    execute('setup_rabbitmq_cluster', True)
    fixup_restart_haproxy_in_all_cfgm(1)
    execute('restart_cfgm')
    execute('upgrade_collector', from_rel, pkg)
    execute('upgrade_control', from_rel, pkg)
    execute('upgrade_webui', from_rel, pkg)
    execute('upgrade_compute', from_rel, pkg)
    # Adding config, database and analytics nodes to api-server
    if float(from_rel) < 2.2:
        execute('prov_config_node')
        execute('prov_database_node')
        execute('prov_analytics_node')
    execute('compute_reboot')
    #Clear the connections cache
    connections.clear()
    execute('restart_openstack_compute')

@task
@roles('build')
def upgrade_without_openstack(from_rel, pkg):
    """Upgrades all the  contrail packages in all nodes except openstack node as per the role definition.
    """
    execute('upgrade_contrail', from_rel, pkg, orch='no')

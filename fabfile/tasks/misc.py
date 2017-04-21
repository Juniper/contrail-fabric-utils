import os
import re
import uuid
import socket

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro
from fabfile.utils.host import get_control_host_string, hstr_to_ip,\
    get_env_passwords, get_authserver_credentials
from fabfile.utils.cluster import get_nodes_to_upgrade_pkg, reboot_nodes
from fabfile.tasks.helpers import reboot_node
from fabfile.tasks.install import create_install_repo_node,\
         install_interface_name_node, install_vrouter_node, apt_install, \
         install_net_driver_node
from fabfile.utils.multitenancy import get_mt_opts
from fabfile.utils.cluster import get_orchestrator, get_mode

@task
def add_vrouter_node(*args):
    """Adds one/more new compute node to the existing cluster."""
    for host_string in args:
        with settings(host_string=host_string):
            execute("create_install_repo_node", env.host_string)
            dpdk = getattr(env, 'dpdk', None)
            execute("install_vrouter_node", env.host_string)
            execute("install_net_driver_node", env.host_string)
            if getattr(env, 'interface_rename', True):
                print "Installing interface Rename package and rebooting the system."
                execute("install_interface_name_node", env.host_string)
                #Clear the connections cache
                connections.clear()
            execute("setup_interface_node", env.host_string)
            execute("add_static_route_node", env.host_string)
            execute("setup_vrouter_node", env.host_string)
            execute("reboot_node", 'yes', env.host_string)

@task
def add_vcenter_compute_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            execute("create_install_repo_node", env.host_string)
            execute("install_vcenter_compute_node", env.host_string)
            execute("setup_vcenter_compute_node", env.host_string)

@task
def detach_vrouter_node(*args):
    """Detaches one/more compute node from the existing cluster."""
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
    cfgm_ip = hstr_to_ip(cfgm_host)
    nova_compute = "openstack-nova-compute"

    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo("service supervisor-vrouter stop")
            if detect_ostype() in ['ubuntu']:
                nova_compute = "nova-compute"
            mode = get_mode(host_string)
            if (mode == 'vcenter'):
                nova_compute = ""
            if (nova_compute != ""):
                sudo("service %s stop" % nova_compute)
            compute_hostname = sudo("hostname")
        with settings(host_string=env.roledefs['cfgm'][0], pasword=cfgm_host_password):
            sudo("python /opt/contrail/utils/provision_vrouter.py --host_name %s --host_ip %s --api_server_ip %s --oper del %s" %
                (compute_hostname, host_string.split('@')[1], cfgm_ip, get_mt_opts()))
    execute("restart_control")

@task
@roles('build')
def check_and_kill_zookeeper():
    for host_string in env.roledefs['database']:
        with settings(host_string=host_string, warn_only=True):
            pkg_rls = get_release('zookeeper')
            if pkg_rls in ['3.4.3']: 
                print 'Killing existing zookeeper process'
                sudo('pkill -f zookeeper')
                sleep(3)
            sudo('ps -ef | grep zookeeper')

@task
@roles('database')
def zoolink():
    """Creates /usr/bin/zookeeper link to /etc/zookeeper"""
    execute("zoolink_node", env.host_string)

@task
def zoolink_node(*args):
    """Creates /usr/bin/zookeeper link to /etc/zookeeper"""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            dirinfo = sudo('ls -lrt /usr/etc/zookeeper')
            link_req = sudo('ls /etc/zookeeper/conf').failed
        if not '/usr/etc/zookeeper -> /etc/zookeeper' in dirinfo and link_req:
            sudo('ln -s /etc/zookeeper /usr/etc/zookeeper')
            sleep(3)
            sudo('ls -lrt /usr/etc/zookeeper')

def replace_vrouterko(distro):
    """Removes the vrouter kernal module."""
    if distro in ['ubuntu']:
        rmmod = 'modprobe -r vrouter || rmmod vrouter'
        insmod = 'modprobe vrouter; service supervisor-vrouter start'
    else:
        rmmod = 'rmmod vrouter'
        insmod = 'service supervisor-vrouter start'
    cmds = ["service supervisor-vrouter stop", rmmod, insmod]
    sudo('; '.join(cmds))


@task
@parallel
@roles('compute')
def replace_vrouter_ko():
    """Replaces the vrouter kernal module with upgraded version."""
    os_type = detect_ostype()
    if os_type in ['ubuntu']:
        cmd = "ls /opt/contrail/contrail_install_repo/contrail-vrouter-$(uname -r)*"
        out = sudo(cmd, warn_only=True)
        #No change in Kernel version so no need to reboot the box.
        if out.succeeded:
            execute('replace_vrouter_ko_node', env.host_string)
        else:
            execute("reboot_node", 'yes', env.host_string)
    else:
        execute("reboot_node", 'yes', env.host_string)

@task
def replace_vrouter_ko_node(*args):
    """Replaces the vrouter kernal module in one compute node."""
    for host_string in args:
        with settings(host_string=host_string):
            replace_vrouterko(detect_ostype())

# Deprecated from Release 3.00; Consider using replace_vrouter_ko
@task
@roles('compute')
def rmmod_vrouter():
    """Removes the vrouter kernal module."""
    execute('rmmod_vrouter_node', env.host_string)

# Deprecated from Release 3.00; Consider using replace_vrouter_ko_node
@task
def rmmod_vrouter_node(*args):
    """Removes the vrouter kernal module in one compute node."""
    for host_string in args:
        with settings(host_string=host_string):
            replace_vrouterko(detect_ostype())


@task
def run_cmd(host_string,cmd):
    with settings(host_string=host_string):
        sudo(cmd)

@task
@hosts(*env.roledefs['cfgm'][:1])
def create_default_secgrp_rules():
    try:
        from vnc_api import vnc_api
        from vnc_api.gen.resource_xsd import PolicyRuleType, PolicyEntriesType, AddressType, PortType, SubnetType
    except ImportError:
        print "Task [create_default_secgrp_rules] can be executed only from the cfgm node"
        return
    vnc_api_ip = env.roledefs['cfgm'][0]
    vnc_api_port = 8082
    auth_user, auth_passwd =  get_authserver_credentials()
    auth_tenant = 'admin'
    try:
        vnc_lib = vnc_api.VncApi(
            api_server_host=vnc_api_ip,
            api_server_port=vnc_api_port,
            username=auth_user,
            password=auth_passwd,
            tenant_name=auth_tenant)
    except Exception ,err:
        print "Unable to connect to API-server %s:%s, as %s/%s" % (vnc_api_ip, vnc_api_port, auth_user, auth_passwd)
        print "ERROR: \n%s" % err

    projects = vnc_lib.projects_list()['projects']
    project_ids = set([proj['uuid'] for proj in projects])
    for proj_uuid in project_ids:
        proj_obj = vnc_lib.project_read(id=proj_uuid)

        security_groups = proj_obj.get_security_groups()
        if not security_groups:
            continue
        for sg in security_groups:
            sg_obj = vnc_lib.security_group_read(id=sg['uuid'])
            if sg_obj.name != 'default':
                continue

            sg_rules = sg_obj.security_group_entries
            ingress_rule_exists = False
            egress_rule_exists = False
            for rule in sg_rules.get_policy_rule():
                if (len(rule.get_src_addresses()) == 1 and
                    rule.get_src_addresses()[0].get_security_group() and
                    rule.get_src_addresses()[0].get_security_group().endswith(':default') and
                    len(rule.get_dst_addresses()) == 1 and
                    rule.get_dst_addresses()[0].get_security_group() and
                    rule.get_dst_addresses()[0].get_security_group() == 'local' and
                    len(rule.get_src_ports()) == 1 and
                    rule.get_src_ports()[0].get_start_port() == 0 and
                    rule.get_src_ports()[0].get_end_port() == 65535 and
                    len(rule.get_dst_ports()) == 1 and
                    rule.get_dst_ports()[0].get_start_port() == 0 and
                    rule.get_dst_ports()[0].get_end_port() == 65535 and
                    rule.get_protocol() == 'any'):
                    print "Default Ingress rule exists in project %s" % proj_obj.name
                    ingress_rule_exists = True
                    if egress_rule_exists:
                        break
                elif (len(rule.get_src_addresses()) == 1 and
                    rule.get_src_addresses()[0].get_security_group() and
                    rule.get_src_addresses()[0].get_security_group() == 'local' and
                    len(rule.get_dst_addresses()) == 1 and
                    rule.get_dst_addresses()[0].get_subnet() and
                    rule.get_dst_addresses()[0].get_subnet().get_ip_prefix() == '0.0.0.0' and
                    len(rule.get_src_ports()) == 1 and
                    rule.get_src_ports()[0].get_start_port() == 0 and
                    rule.get_src_ports()[0].get_end_port() == 65535 and
                    len(rule.get_dst_ports()) == 1 and
                    rule.get_dst_ports()[0].get_start_port() == 0 and
                    rule.get_dst_ports()[0].get_end_port() == 65535 and
                    rule.get_protocol() == 'any'):
                    print "Default Egress rule exists in project %s" % proj_obj.name
                    egress_rule_exists = True
                    if ingress_rule_exists:
                        break

            sgr_uuid = str(uuid.uuid4())
            ingress_rule = PolicyRuleType(rule_uuid=sgr_uuid, direction='>',
                                          protocol='any',
                                          src_addresses=[
                                              AddressType(
                                                  security_group=proj_obj.get_fq_name_str() + ':' + 'default')],
                                          src_ports=[PortType(0, 65535)],
                                          dst_addresses=[
                                              AddressType(security_group='local')],
                                          dst_ports=[PortType(0, 65535)])

            if not ingress_rule_exists:
                print "Default Ingress rule doesn't exists in project %s" % proj_obj.name
                sg_rules.add_policy_rule(ingress_rule)

            sgr_uuid = str(uuid.uuid4())
            egress_rule = PolicyRuleType(rule_uuid=sgr_uuid, direction='>',
                                         protocol='any',
                                         src_addresses=[
                                             AddressType(security_group='local')],
                                         src_ports=[PortType(0, 65535)],
                                         dst_addresses=[
                                             AddressType(
                                                 subnet=SubnetType('0.0.0.0', 0))],
                                         dst_ports=[PortType(0, 65535)])
            if not egress_rule_exists:
                print "Default Egress rule doesn't exists in project %s" % proj_obj.name
                sg_rules.add_policy_rule(egress_rule)

            # update security group
            sg_obj.security_group_entries = sg_rules
            vnc_lib.security_group_update(sg_obj)
            print "Updated default security group rules in project %s" % proj_obj.name
# end create_default_secgrp_rules

@task
@roles('build')
def setup_passwordless_ssh(*args):
    id_rsa_pubs = {}
    for host_string in args:
        with settings(host_string=host_string):
            if files.exists('~/.ssh', use_sudo=True):
                sudo('chmod 700 ~/.ssh')
            if (not files.exists('~/.ssh/id_rsa', use_sudo=True) and
                not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
                sudo('ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')
            elif (not files.exists('~/.ssh/id_rsa', use_sudo=True) or
                  not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
                sudo('rm -rf ~/.ssh/id_rsa ~/.ssh/id_rsa.pub')
                sudo('ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')
            id_rsa_pubs.update({host_string : sudo('cat ~/.ssh/id_rsa.pub')})
    for host_string in args:
        with settings(host_string=host_string):
            for host, id_rsa_pub in id_rsa_pubs.items():
                files.append('~/.ssh/authorized_keys',
                             id_rsa_pub, use_sudo=True)
            sudo('chmod 640 ~/.ssh/authorized_keys')
# end setup_passwordless_ssh


@task
def add_reserved_ports_node(ports, *args):
    for host_string in args:
        with settings(host_string=host_string):
            # Exclude ports from the available ephemeral port range
            existing_ports = sudo("cat /proc/sys/net/ipv4/ip_local_reserved_ports")
            sudo("sysctl -w net.ipv4.ip_local_reserved_ports=%s,%s" % (ports, existing_ports))
            # Make the exclusion of port 35357 persistent
            with settings(warn_only=True):
                not_set = sudo("grep '^net.ipv4.ip_local_reserved_ports' /etc/sysctl.conf > /dev/null 2>&1").failed
            if not_set:
                sudo('echo "net.ipv4.ip_local_reserved_ports = %s" >> /etc/sysctl.conf' % ports)
            else:
                sudo("sed -i 's/net.ipv4.ip_local_reserved_ports\s*=\s*/net.ipv4.ip_local_reserved_ports=%s,/' /etc/sysctl.conf" % ports)

            # Centos returns non zero return code for "sysctl -p".
            # However the ports are reserved properly.
            with settings(warn_only=True):
                sudo("sysctl -p")

@task
@EXECUTE_TASK
@roles('openstack')
def add_openstack_reserved_ports():
    if env.roledefs['openstack']:
        ports = '35357,35358,33306,9322'
        execute('add_reserved_ports_node', ports, env.host_string)


@task
@roles('build')
def upgrade_biosdevname_all(reboot='yes'):
    """creates repo and upgrades biosdevname in Ubuntu"""
    execute('pre_check')
    execute('create_install_repo')
    nodes = []
    with settings(host_string=env.roledefs['all'][0], warn_only=True):
        dist, version, extra = get_linux_distro()
        if version == '14.04':
            (package, os_type) = ('biosdevname', 'ubuntu')
    nodes = get_nodes_to_upgrade_pkg(package, os_type,
                *env.roledefs['all'], version='0.4.1-0ubuntu6.1')
    if not nodes:
        print "biosdevname is already of expected version"
        return
    execute(upgrade_biosdevname_node, *nodes)
    if reboot == 'yes':
        node_list_except_build = list(nodes)
        if env.host_string in nodes:
            node_list_except_build.remove(env.host_string)
            reboot_nodes(*node_list_except_build)
            reboot_nodes(env.host_string)
        else:
            reboot_nodes(*nodes)

@task
def upgrade_biosdevname_node(*args):
    """upgrades the biosdevname in given nodes."""
    for host_string in args:
        with settings(host_string=host_string):
            print "upgrading biosdevname package"
            apt_install(["biosdevname"])

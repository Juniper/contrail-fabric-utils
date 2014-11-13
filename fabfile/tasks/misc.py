import os
import re
import uuid
import socket

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.tasks.helpers import reboot_node
from fabfile.utils.host import get_control_host_string, hstr_to_ip
from fabfile.tasks.provision import setup_vrouter_node, get_openstack_credentials
from fabfile.tasks.install import create_install_repo_node, install_interface_name_node, install_vrouter_node

@task
def add_vrouter_node(*args):
    """Adds one/more new compute node to the existing cluster."""
    for host_string in args:
        with settings(host_string=host_string):
            execute("create_install_repo_node", env.host_string)
            execute("install_vrouter_node", env.host_string)
            if getattr(env, 'interface_rename', True):
                print "Installing interface Rename package and rebooting the system."
                execute("install_interface_name_node", env.host_string)
                #Clear the connections cache
                connections.clear()
            execute("setup_interface_node", env.host_string)
            execute("add_static_route_node", env.host_string)
            execute("upgrade_pkgs_node", env.host_string)
            execute("setup_vrouter_node", env.host_string)
            execute("reboot_node", env.host_string)


@task
def detach_vrouter_node(*args):
    """Detaches one/more compute node from the existing cluster."""
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
    cfgm_ip = hstr_to_ip(cfgm_host)
    nova_compute = "openstack-nova-compute"
    if detect_ostype() in ['ubuntu']:
        nova_compute = "nova-compute"

    for host_string in args:
        compute_hostname = socket.gethostbyaddr(hstr_to_ip(host_string))[0].split('.')[0]
        with settings(host_string=host_string, warn_only=True):
            sudo("service supervisor-vrouter stop")
            sudo("service %s stop" % nova_compute)
        with settings(host_string=cfgm_host, pasword=cfgm_host_password):
            sudo("python /opt/contrail/utils/provision_vrouter.py --host_name %s --host_ip %s --api_server_ip %s --oper del" %
                (compute_hostname, host_string.split('@')[1], cfgm_ip))
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


@task
@roles('compute')
def rmmod_vrouter():
    """Removes the vrouter kernal module."""
    execute('rmmod_vrouter_node', env.host_string)

@task
def rmmod_vrouter_node(*args):
    """Removes the vrouter kernal module in one compoute node."""
    for host_string in args:
        if getattr(testbed, 'data', None) and host_string in testbed.data.keys():
            with settings(host_string=host_string):
                sudo("service supervisor-vrouter stop")
                sudo("rmmod vrouter")
                sudo("insmod /lib/modules/3.8.0-29-generic/extra/net/vrouter/vrouter.ko")
                sudo("service supervisor-vrouter start")
        else:
            print "Managment and data interface are the same."

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
    auth_user, auth_passwd =  get_openstack_credentials()
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
            if files.exists('/root/.ssh'):
                sudo('chmod 700 /root/.ssh')
            if not files.exists('/root/.ssh/id_rsa') and not files.exists('/root/.ssh/id_rsa.pub'):
                sudo('ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N ""')
            elif not files.exists('/root/.ssh/id_rsa') or not files.exists('/root/.ssh/id_rsa.pub'):
                sudo('rm -rf /root/.ssh/id_rsa*')
                sudo('ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N ""')
            id_rsa_pubs.update({host_string : sudo('cat /root/.ssh/id_rsa.pub')})
    for host_string in args:
        with settings(host_string=host_string):
            for host, id_rsa_pub in id_rsa_pubs.items():
                files.append('/root/.ssh/authorized_keys', id_rsa_pub)
            sudo('chmod 640 /root/.ssh/authorized_keys')
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

@task
@EXECUTE_TASK
@roles('openstack')
def add_openstack_reserverd_ports():
    ports = '35357,35358,33306'
    execute('add_reserved_ports_node', ports, env.host_string)

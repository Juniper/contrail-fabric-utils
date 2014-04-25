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
            execute("install_interface_name_node", env.host_string)
            #Clear the connections cache
            connections.clear()
            execute("upgrade_pkgs_node", env.host_string)
            execute("setup_vrouter_node", env.host_string)
            execute("reboot_node", env.host_string)


@task
def detach_vrouter_node(*args):
    """Detaches one/more compute node from the existing cluster."""
    cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
    cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
    cfgm_ip = hstr_to_ip(cfgm_host)

    for host_string in args:
        compute_hostname = socket.gethostbyaddr(hstr_to_ip(host_string))[0].split('.')[0]
        with settings(host_string=host_string, warn_only=True):
            run("service supervisor-vrouter stop")
        with settings(host_string=cfgm_host, pasword=cfgm_host_password):
            run("python /opt/contrail/utils/provision_vrouter.py --host_name %s --host_ip %s --api_server_ip %s --oper del" %
                (compute_hostname, host_string.split('@')[1], cfgm_ip))
    execute("restart_control")

@task
@roles('build')
def check_and_kill_zookeeper():
    for host_string in env.roledefs['cfgm']:
        with settings(host_string=host_string, warn_only=True):
            pkg_rls = get_release('zookeeper')
            if pkg_rls in ['3.4.3']: 
                print 'Killing existing zookeeper process'
                run('pkill -f zookeeper')
                sleep(3)
            run('ps -ef | grep zookeeper')

@task
@roles('cfgm')
def zoolink():
    """Creates /usr/bin/zookeeper link to /etc/zookeeper"""
    execute("zoolink_node", env.host_string)

@task
def zoolink_node(*args):
    """Creates /usr/bin/zookeeper link to /etc/zookeeper"""
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            dirinfo = run('ls -lrt /usr/etc/zookeeper')
            link_req = run('ls /etc/zookeeper/conf').failed
        if not '/usr/etc/zookeeper -> /etc/zookeeper' in dirinfo and link_req:
            run('ln -s /etc/zookeeper /usr/etc/zookeeper')
            sleep(3)
            run('ls -lrt /usr/etc/zookeeper')


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
                run("service supervisor-vrouter stop")
                run("rmmod vrouter")
                run("insmod /lib/modules/3.8.0-29-generic/extra/net/vrouter/vrouter.ko")
                run("service supervisor-vrouter start")
        else:
            print "Managment and data interface are the same."

@task
def run_cmd(host_string,cmd):
    with settings(host_string=host_string):
        run(cmd)

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
        print "Unable to connect to API-server %s:%s, as %s/%s" % (vnc_api_ip, vnc_api_port, auth_user, auth_password)
        print "ERROR: \n%s" % err

    projects = vnc_lib.projects_list()['projects']
    project_ids = set([proj['uuid'] for proj in projects])
    for proj_uuid in project_ids:
        proj_obj = vnc_lib.project_read(id=proj_uuid)

        security_groups = proj_obj.get_security_groups()
        if not security_groups:
            continue
        for sg in security_groups
            sg_obj = vnc_lib.security_group_read(id=sg['uuid'])
            if sg_obj.name != 'default':
                continue

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
            sg_rules = PolicyEntriesType([ingress_rule])

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
            sg_rules.add_policy_rule(egress_rule)

            # update security group
            sg_obj.security_group_entries = sg_rules
            vnc_lib.security_group_update(sg_obj)
            print "Updated default security group rules in project %s" % proj_obj.name
# end create_default_secgrp_rules


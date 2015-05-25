import os
import string
import textwrap
import json
import socket
from time import sleep

from fabric.contrib.files import exists

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.utils.migration import *
from fabfile.utils.storage import *
from fabfile.utils.analytics import *
from fabfile.utils.config import get_value
from fabfile.tasks.install import *
from fabfile.tasks.verify import *
from fabfile.tasks.helpers import *
from fabfile.utils.vcenter import *
from fabfile.utils.commandline import *
from fabfile.tasks.tester import setup_test_env
from fabfile.tasks.rabbitmq import setup_rabbitmq_cluster
from fabfile.tasks.vmware import provision_vcenter, provision_dvs_fab,\
        configure_esxi_network, create_esxi_compute_vm
from fabfile.utils.cluster import get_vgw_details, get_orchestrator,\
        get_vmware_details, get_tsn_nodes, get_toragent_nodes,\
        get_esxi_vms_and_hosts
from fabfile.tasks.esxi_defaults import apply_esxi_defaults

FAB_UTILS_DIR = '/opt/contrail/utils/fabfile/utils/'

@task
@roles('all')
def setup_common():
    self_ip = hstr_to_ip(get_control_host_string(env.host_string))
    ntp_server = get_ntp_server()
    cmd = 'setup-vnc-common'
    cmd += ' --self_ip %s' % self_ip
    if ntp_server:
        cmd += ' --ntp_server %s' % ntp_server

    sudo(cmd)

@task
@EXECUTE_TASK
@roles('cfgm')
def setup_cfgm():
    """Provisions config services in all nodes defined in cfgm role."""
    if env.roledefs['cfgm']:
        execute("setup_cfgm_node", env.host_string)

@task
def setup_cfgm_node(*args):
    """Provisions config services in one or list of nodes. USAGE: fab setup_cfgm_node:user@1.1.1.1,user@2.2.2.2"""

    for host_string in args:
        with  settings(host_string=host_string):
            # Frame the command line to provision config node
            cmd = frame_vnc_config_cmd(host_string)
            # Execute the provision config script
            sudo(cmd)
#end setup_cfgm_node

@task
@EXECUTE_TASK
@roles('cfgm')
def setup_vcenter_plugin():
    """Provisions vcenter plugin services in all nodes defined in cfgm role."""
    orch = get_orchestrator()
    if orch == 'vcenter':
        if env.roledefs['cfgm']:
            execute("setup_vcenter_plugin_node", env.host_string)
@task
def setup_vcenter_plugin_node(*args):
    """Provisions vcenter plugin services in one or list of nodes. USAGE: fab setup_cfgm_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        with  settings(host_string=host_string):
            # Frame the command  to provision vcenter-plugin
            cmd = frame_vnc_vcenter_plugin_cmd(host_string)
            # Execute the provision vcenter-plugin script
            sudo(cmd)

def fixup_mongodb_conf_file():
    sudo("service mongodb stop")
    sudo("sed -i -e '/^[ ]*bind/s/^/#/' /etc/mongodb.conf")
    with settings(warn_only=True):
        output = sudo("grep replSet=rs-ceilometer /etc/mongodb.conf")
    if not output.succeeded:
        sudo("echo \"replSet=rs-ceilometer\" >> /etc/mongodb.conf")
    sudo("service mongodb start")
    # check if the mongodb is running, if not, issue start again
    count = 1
    cmd = "service mongodb status | grep not"
    with settings(warn_only=True):
        output = sudo(cmd)
    while output.succeeded:
        count += 1
        if count > 10:
            break
        sleep(1)
        sudo("service mongodb restart")
        with settings(warn_only=True):
            output = sudo(cmd)
#end fixup_mongodb_conf_file

def setup_ceilometer_mongodb(ip, mongodb_ip_list):
    # Configure replicaSet only on the first mongodb node
    if ip == mongodb_ip_list[0]:
        # Verify that we are able to connect
        cmd = "mongo --host " + ip + " --quiet --eval " + \
            "'db = db.getSiblingDB(\"ceilometer\")'"
        verify_command_succeeded(cmd = cmd, expected_output = "ceilometer",
                                 error_str = "Not able to connect to mongodb",
                                 max_count = 10, sleep_interval = 1,
                                 warn_only = True)
        # Verify if replicaSet is already configured
        cmd = "mongo --host " + ip + " --quiet --eval 'rs.conf()._id'"
        with settings(warn_only=True):
            output = sudo(cmd)
        if output.succeeded and output == 'rs-ceilometer':
            return
        cmd = "mongo --host " + ip + " --quiet --eval " + \
            "'rs.initiate({_id:\"rs-ceilometer\", " + \
            "members:[{_id:0, host:\"" + ip + ":27017\"}]}).ok'"
        verify_command_succeeded(cmd = cmd, expected_output = "1",
                                 error_str = "Not able to initiate replicaSet",
                                 max_count = 1, sleep_interval = 1,
                                 warn_only = False)
        # Verify that we are adding on primary
        cmd = "mongo --host " + ip + " --quiet --eval 'db.isMaster().ismaster'"
        verify_command_succeeded(cmd = cmd, expected_output = "true",
                                 error_str = "Not primary",
                                 max_count = 30, sleep_interval = 2,
                                 warn_only = False)
        # Add replicaSet members
        for other_ip in mongodb_ip_list:
            if ip == other_ip:
                continue
            cmd = "mongo --host " + ip + \
                " --quiet --eval 'rs.add(\"" + other_ip + ":27017\").ok'"
            verify_command_succeeded(cmd = cmd, expected_output = "1",
                                     error_str = "Not able to add " + \
                                         other_ip + " to replicaSet",
                                     max_count = 1, sleep_interval = 1,
                                     warn_only = False)
        # Verify replicaSet status and members
        cmd = "mongo --host " + ip + " --quiet --eval 'rs.status().ok'"
        verify_command_succeeded(cmd = cmd, expected_output = "1",
                                 error_str = "replicaSet status NOT OK",
                                 max_count = 10, sleep_interval = 1,
                                 warn_only = False)
        cmd = "mongo --host " + ip + " --quiet --eval " + \
            "'rs.status().members.length'"
        verify_command_succeeded(cmd = cmd,
                                 expected_output = str(len(mongodb_ip_list)),
                                 error_str = "replicaSet does not contain "
                                     "all database nodes",
                                 max_count = 1, sleep_interval = 1,
                                 warn_only = False)
        # check if ceilometer user has already been added
        cmd = "mongo --host " + ip + " --quiet --eval " + \
            "\"db.system.users.find({'user':'ceilometer'}).count()\" ceilometer"
        output = sudo(cmd)
        # Does user ceilometer exist
        if output == "1":
            return
        cmd = "mongo --host " + ip + " --eval " + \
            "'db = db.getSiblingDB(\"ceilometer\"); " + \
            "db.addUser({user: \"ceilometer\", pwd: \"CEILOMETER_DBPASS\", " + \
            "roles: [ \"readWrite\", \"dbAdmin\" ]})'"
        if not sudo(cmd).succeeded:
            raise RuntimeError("Not able to add ceilometer mongodb user")
#end setup_ceilometer_mongodb

@task
@roles('openstack')
def setup_contrail_ceilometer_plugin():
    """Provisions contrail ceilometer plugin in the first node defined in openstack role."""
    if env.roledefs['openstack'] and env.host_string == env.roledefs['openstack'][0]:
        execute("setup_contrail_ceilometer_plugin_node", env.host_string)

@task
def setup_contrail_ceilometer_plugin_node(*args):
    """Provisions contrail ceilometer plugin in one or list of nodes.
       USAGE: fab setup_contrail_ceilometer_plugin_node:user@1.1.1.1,user@2.2.2.2"""
    analytics_ip = hstr_to_ip(env.roledefs['collector'][0])
    for host_string in args:
        with settings(host_string=host_string):
            # Fixup ceilometer pipeline.yaml cfg
            fixup_ceilometer_pipeline_conf(analytics_ip)
            os_type = detect_ostype()
            if os_type == 'ubuntu':
                ceilometer_services = ['ceilometer-agent-central']
            elif os_type in ['redhat']:
                ceilometer_services = ['openstack-ceilometer-central']
            else:
                raise RuntimeError("Unsupported OS Type (%s)", os_type)
            for svc in ceilometer_services:
                sudo("service %s restart" % (svc))

@task
@roles('openstack')
def setup_openstack():
    """Provisions openstack services in all nodes defined in openstack role."""
    if env.roledefs['openstack']:
        execute("setup_openstack_node", env.host_string)

@task
@roles('openstack')
def setup_nova_aggregate():
    if get_orchestrator() == 'vcenter':
        return
    if env.roledefs['openstack'].index(env.host_string) == 0:
        # Copy only once in a HA setup
        copy_openstackrc()
    execute('setup_nova_aggregate_node', env.host_string)

@task
def setup_nova_aggregate_node(*args):
    docker = any(['docker' == get_hypervisor(compute_host)
                  for compute_host in env.roledefs['compute']])
    libvirt = any(['libvirt' == get_hypervisor(compute_host)
                  for compute_host in env.roledefs['compute']])
    if not (libvirt and docker):
        # Not a hybrid setup(libvirt + docker)
        # No need for the compute aggregate
        return

    for compute_host in env.roledefs['compute']:
        hypervisor = get_hypervisor(compute_host)
        host_name = None
        for i in range(5):
            try:
                host_name = socket.gethostbyaddr(
                    hstr_to_ip(compute_host))[0].split('.')[0]
            except socket.herror:
                sleep(5)
                continue
            else:
                break
        if not host_name:
            raise RuntimeError("Not able to get the hostname of compute host:%s", compute_host)
        if hypervisor == 'docker':
            retry = 10
            while retry:
                with settings(warn_only=True):
                    aggregate_list = sudo("(source /etc/contrail/openstackrc; nova aggregate-list)")
                if aggregate_list.failed:
                    sleep(6)
                    retry -= 1
                    continue
                break
            if hypervisor not in aggregate_list:
                sudo("(source /etc/contrail/openstackrc; nova aggregate-create %s nova/%s)" % (hypervisor, hypervisor))
            sudo("(source /etc/contrail/openstackrc; nova aggregate-add-host %s %s)" % (hypervisor, host_name))

@task
def setup_openstack_node(*args):
    """Provisions openstack services in one or list of nodes. USAGE: fab setup_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # Frame the command line to provision openstack
        cmd = frame_vnc_openstack_cmd(host_string)
        # Execute the provision openstack script
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_openstack_node

@task
@EXECUTE_TASK
@roles('collector')
def setup_collector():
    """Provisions collector services in all nodes defined in collector role."""
    if env.roledefs['collector']:
        execute("setup_collector_node", env.host_string)

@task
def setup_collector_node(*args):
    """Provisions collector services in one or list of nodes. USAGE: fab setup_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # Frame the command line to provision collector
        cmd = frame_vnc_collector_cmd(host_string)
        # Execute the provision collector script
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_collector

@task
@EXECUTE_TASK
@roles('database')
def fixup_mongodb_conf():
    """Fixup configuration file for mongodb in all nodes defined in database
       role if ceilometer provisioning is supported.
    """
    if (env.roledefs['database'] and
        is_ceilometer_provision_supported(use_install_repo=True)):
        execute("fixup_mongodb_conf_node", env.host_string)

@task
def fixup_mongodb_conf_node(*args):
    """Fixup configuration file for mongodb in one or list of nodes.
       USAGE: fab fixup_mongodb_conf_node:user@1.1.1.1,user@2.2.2.2
    """
    for host_string in args:
        with settings(host_string=host_string):
            fixup_mongodb_conf_file()

@task
@roles('database')
def setup_mongodb_ceilometer_cluster():
    """Provisions mongodb ceilometer cluster consisting of all nodes defined
       in database role if ceilometer provisioning is supported.
    """
    # Configure only on the first mongodb node
    if (env.roledefs['database'] and
            is_ceilometer_provision_supported(use_install_repo=True) and
            env.host_string == env.roledefs['database'][0]):
        database_ip = hstr_to_ip(get_control_host_string(env.host_string))
        database_host_list = [get_control_host_string(entry)\
                                  for entry in env.roledefs['database']]
        database_ip_list = [hstr_to_ip(db_host) for db_host in database_host_list]
        with settings(host_string=env.host_string):
            setup_ceilometer_mongodb(database_ip, database_ip_list)

@task
@roles('database')
def setup_database():
    """Provisions database services in all nodes defined in database role."""
    if env.roledefs['database']:
        execute("setup_database_node", env.host_string)

@task
def setup_database_node(*args):
    """Provisions database services in one or list of nodes. USAGE: fab setup_database_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # Frame the command line to provision database
        cmd = frame_vnc_database_cmd(host_string)
        # Execute the provision database script
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_database

@task
@EXECUTE_TASK
@roles('webui')
def setup_webui():
    """Provisions webui services in all nodes defined in webui role."""
    if env.roledefs['webui']:
        execute("setup_webui_node", env.host_string)

@task
def setup_webui_node(*args):
    """Provisions webui services in one or list of nodes. USAGE: fab setup_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # Frame the command line to provision webui
        cmd = frame_vnc_webui_cmd(host_string)
        # Execute the provision webui script
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_webui

@task
@EXECUTE_TASK
@roles('control')
def setup_control():
    """Provisions control services in all nodes defined in control role."""
    if env.roledefs['control']:
        execute("setup_control_node", env.host_string)

@task
def setup_control_node(*args):
    """Provisions control services in one or list of nodes. USAGE: fab setup_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        cmd = frame_vnc_control_cmd(host_string)
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_control

@task
@EXECUTE_TASK
@roles('compute')
def setup_agent_config():
    if env.roledefs['compute']:
        execute("setup_agent_config_in_node", env.host_string)

@task
def setup_agent_config_in_node(*args):
    agent_conf_file = "/etc/contrail/contrail-vrouter-agent.conf"
    restart_service = False

    # Set flow cache timeout in secs, default is 180...
    for host_string in args:
        try:
            if (getattr(env, 'flow_cache_timeout', None)):
                flow_cache_set_cmd = "flow_cache_timeout=%s" %(env.flow_cache_timeout)
                restart_service = True
                with settings(host_string=host_string):
                    out = sudo("grep flow_cache_timeout %s" %(agent_conf_file))
                    sudo("sed -i \"s|%s|%s|\" %s" %(out, flow_cache_set_cmd, agent_conf_file))
                    sudo("grep flow_cache_timeout %s" %(agent_conf_file))
        except Exception:
            pass

    # Set per_vm_flow_limit as %, default is 100...
    for host_string in args:
        try:
            if (getattr(env, 'max_vm_flows', None)):
                max_vm_flows_set_cmd = "max_vm_flows=%s" %(env.max_vm_flows)
                restart_service = True
                with settings(host_string=host_string):
                    out = sudo("grep max_vm_flows %s" %(agent_conf_file))
                    sudo("sed -i \"s|%s|%s|\" %s" %(out, max_vm_flows_set_cmd, agent_conf_file))
                    sudo("grep max_vm_flows %s" %(agent_conf_file))
        except Exception:
            pass

    # After setting all agent parameters, restart service...
    if restart_service:
        for host_string in args:
            with settings(host_string=host_string):
                out = sudo("service supervisor-vrouter restart")

# end setup_agent_config_in_node

@task
@EXECUTE_TASK
@roles('compute')
def setup_vrouter(manage_nova_compute='yes', configure_nova='yes'):
    """Provisions vrouter services in all nodes defined in vrouter role.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
       Even when we are no managing nova-compute (manage_nova_compute = no) still we execute few required config on
       nova.conf. If configure_nova = no; No nova config related configuration will executed on nova.conf file.
    """
    manage_nova_compute = get_manage_nova_compute(manage_nova_compute)
    configure_nova = get_configure_nova(configure_nova)
    if env.roledefs['compute']:
       if get_orchestrator() == 'vcenter':
           manage_nova_compute='no'
           configure_nova='no'
       execute("setup_only_vrouter_node", 
               manage_nova_compute,
               configure_nova,
               env.host_string)

@task
def setup_vrouter_node(*args):
    """Provisions nova-compute and vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute("setup_only_vrouter_node", 'yes', 'yes', *args)

@task
def setup_only_vrouter_node(manage_nova_compute='yes', configure_nova='yes', *args):
    """Provisions only vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
    """
    #metadata_secret = None
    #orch = get_orchestrator()
    #if orch == 'openstack':
    #    ## reset openstack connections to create new connections
    #    ## when running in parallel mode
    #    #openstack_host = env.roledefs['openstack'][0]
    #    #openstack_host_connection = openstack_host + ':22'
    #    #if connections and openstack_host_connection in connections.keys():
    #    #    connections.pop(openstack_host_connection)

    #    # Use metadata_secret provided in testbed. If not available
    #    # retrieve neutron_metadata_proxy_shared_secret from openstack
    #    metadata_secret = getattr(testbed,
    #                              'neutron_metadata_proxy_shared_secret',
    #                              None)
    #    if not metadata_secret:
    #        with settings(host_string=openstack_host):
    #            status, secret = get_value('/etc/nova/nova.conf',
    #                                 'DEFAULT',
    #                                 'service_neutron_metadata_proxy',
    #                                 'neutron_metadata_proxy_shared_secret')
    #        metadata_secret = secret if status == 'True' else None

    for host_string in args:
        # Frame the command line to provision compute node.
        cmd = frame_vnc_compute_cmd(host_string,
                                    manage_nova_compute=manage_nova_compute,
                                    configure_nova=configure_nova)

        # Setup hugepages if necessary
        setup_hugepages_node(host_string)

        # Setup affinity mask if necessary
        setup_coremask_node(host_string)

        # Execute the script to provision compute node.
        with  settings(host_string=host_string):
            sudo(cmd)
#end setup_vrouter

@task
@EXECUTE_TASK
@roles('cfgm')
def prov_config_node():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    tgt_ip = hstr_to_ip(get_control_host_string(env.host_string))
    tgt_hostname = sudo("hostname")

    with cd(UTILS_DIR):
        cmd = "python provision_config_node.py"
        cmd += " --api_server_ip %s" % cfgm_ip
        cmd += " --host_name %s" % tgt_hostname
        cmd += " --host_ip %s" % tgt_ip
        cmd += " --oper add"
        cmd += " %s" % get_mt_opts()
        sudo(cmd)
#end prov_config_node

@task
@EXECUTE_TASK
@roles('database')
def prov_database_node():
    cfgm_host = env.roledefs['cfgm'][0]
    cfgm_ip = hstr_to_ip(get_control_host_string(cfgm_host))
    cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
    tgt_ip = hstr_to_ip(get_control_host_string(env.host_string))
    tgt_hostname = sudo("hostname")

    with settings(cd(UTILS_DIR), host_string=cfgm_host,
                  password=cfgm_host_password):
        cmd = "python provision_database_node.py"
        cmd += " --api_server_ip %s" % cfgm_ip
        cmd += " --host_name %s" % tgt_hostname
        cmd += " --host_ip %s" % tgt_ip
        cmd += " --oper add"
        cmd += " %s" % get_mt_opts()
        sudo(cmd)
#end prov_database_node

@task
@EXECUTE_TASK
@roles('collector')
def prov_analytics_node():
    cfgm_host = env.roledefs['cfgm'][0]
    cfgm_ip = hstr_to_ip(get_control_host_string(cfgm_host))
    cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
    tgt_ip = hstr_to_ip(get_control_host_string(env.host_string))
    tgt_hostname = sudo("hostname")

    with settings(cd(UTILS_DIR), host_string=cfgm_host,
                  password=cfgm_host_password):
        cmd = "python provision_analytics_node.py"
        cmd += " --api_server_ip %s" % cfgm_ip
        cmd += " --host_name %s" % tgt_hostname
        cmd += " --host_ip %s" % tgt_ip
        cmd += " --oper add"
        cmd += " %s" % get_mt_opts()
        sudo(cmd)
#end prov_analytics_node

@task
@EXECUTE_TASK
@roles('control')
def prov_control_bgp():
    cfgm_host = env.roledefs['cfgm'][0]
    cfgm_ip = hstr_to_ip(get_control_host_string(cfgm_host))
    cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
    tgt_ip = hstr_to_ip(get_control_host_string(env.host_string))
    tgt_hostname = sudo("hostname")

    with settings(cd(UTILS_DIR), host_string=cfgm_host,
                  password=cfgm_host_password):
        print "Configuring global system config with the ASN"
        cmd = "python provision_control.py"
        cmd += " --api_server_ip %s" % cfgm_ip
        cmd += " --api_server_port 8082"
        cmd += " --router_asn %s" % testbed.router_asn
        cmd += " %s" % get_mt_opts()
        sudo(cmd)
        print "Adding control node as bgp router"
        cmd += " --host_name %s" % tgt_hostname
        cmd += " --host_ip %s" % tgt_ip
        cmd += " --oper add"
        sudo(cmd)
#end prov_control_bgp

@roles('cfgm')
@task
def prov_external_bgp():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))

    for ext_bgp in testbed.ext_routers:
        ext_bgp_name = ext_bgp[0]
        ext_bgp_ip   = ext_bgp[1]
        with cd(UTILS_DIR):
            cmd = "python provision_mx.py"
            cmd += " --api_server_ip %s" % cfgm_ip
            cmd += " --api_server_port 8082"
            cmd += " --router_name %s" % ext_bgp_name
            cmd += " --router_ip %s" % ext_bgp_ip
            cmd += " --router_asn %s" % testbed.router_asn
            cmd += " %s" % get_mt_opts()
            sudo(cmd)
#end prov_control_bgp

@roles('cfgm')
@task
def prov_metadata_services():
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    orch = get_orchestrator()
    if orch is 'none':
        return

    if orch is 'openstack':
        openstack_host = get_control_host_string(env.roledefs['openstack'][0])
        ipfabric_service_ip = get_openstack_internal_vip() or hstr_to_ip(openstack_host)
        ipfabric_service_port = '8775'
        admin_user, admin_password = get_openstack_credentials()
    elif orch is 'vcenter':
        ipfabric_service_ip = get_vcenter_ip()
        ipfabric_service_port = get_vcenter_port()
        admin_user, admin_password = get_vcenter_credentials()
    metadata_args = "--admin_user %s" % admin_user
    metadata_args += " --admin_password %s" % admin_password
    metadata_args += " --ipfabric_service_ip %s" % ipfabric_service_ip
    metadata_args += " --api_server_ip %s" % cfgm_ip
    metadata_args += " --linklocal_service_name metadata"
    metadata_args += " --linklocal_service_ip 169.254.169.254"
    metadata_args += " --linklocal_service_port 80"
    metadata_args += " --ipfabric_service_port %s" % ipfabric_service_port
    metadata_args += " --oper add"
    sudo("python /opt/contrail/utils/provision_linklocal.py %s" % metadata_args)
#end prov_metadata_services

@roles('cfgm')
@task
def prov_encap_type():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    orch = get_orchestrator()
    if orch is 'none':
        return

    if orch is 'openstack':
        admin_user, admin_password = get_openstack_credentials()
    elif orch is 'vcenter':
        admin_user, admin_password = get_vcenter_credentials()
    if 'encap_priority' not in env.keys():
        env.encap_priority="MPLSoUDP,MPLSoGRE,VXLAN"
    encap_args = "--admin_user %s" % admin_user
    encap_args += " --admin_password %s" % admin_password
    encap_args += " --encap_priority %s" % env.encap_priority
    encap_args += " --oper add"
    sudo("python /opt/contrail/utils/provision_encap.py %s" % encap_args)
    sleep(10)
#end prov_encap_type

@task
@hosts(env.roledefs['all'])
def setup_remote_syslog():
    """Provisions all the configs needed to bring up rsyslog as per the options mentioned
    in the testbed file. USAGE: fab setup_remote_syslog."""
    if env.roledefs['all']:
        execute("setup_remote_syslog_node", env.host_string)

@task
def setup_remote_syslog_node(*args):
    """Provisions all the configs needed to bring up rsyslog as per the options mentioned
    in the testbed file on a single or list of nodes USAGE: fab setup_remote_syslog_node:user@1.1.1.1,user@2.2.2.2"""
    rsyslog_dict = getattr(env, 'rsyslog_params', None)
    if rsyslog_dict is None:
        print "env.rsyslog_params has to be defined and 'status' set to 'enable/disable' to setup/cleanup remote syslog."
        return True

    rsyslog_port = -1
    rsyslog_proto = 'transport protocol for rsyslog'
    # static - connect to a single collector in the topology - Test Only option.
    # dynamic - connect in a round robin to all the available collectors in
    # the topology - Default.
    rsyslog_connection = 'static or dynamic client server connection for syslog'
    default_port = 19876
    default_protocol = 'tcp'
    default_connection = 'dynamic'
    if env.rsyslog_params['status'].lower() == 'enable':
        if 'port' in env.rsyslog_params:
            rsyslog_port = env.rsyslog_params['port']
        else:
            # Hard codded default port number.
            rsyslog_port = default_port

        if 'proto' in env.rsyslog_params:
            rsyslog_proto = env.rsyslog_params['proto'].lower()
            if ((rsyslog_proto != 'udp') and (rsyslog_proto != 'tcp')):
                print "env.rsyslog_params['proto'] has to be 'tcp' or 'udp'."
                return True
        else:
            # Hard codded default protocol udp.
            rsyslog_proto = default_protocol

        if 'collector' in env.rsyslog_params:
            rsyslog_connection = env.rsyslog_params['collector'].lower()
            if ((rsyslog_connection != 'static')
                    and (rsyslog_connection != 'dynamic')):
                print "env.rsyslog_params['collector'] has to be 'static' or 'dynamic'."
                return True
        else:
            # Hard codded default connection is dynamic.
            rsyslog_connection = default_connection

        collector_ips = role_to_ip_dict(
            role='collector')
        all_node_ips = role_to_ip_dict(role='all')
        connect_map_dict = {}
        if rsyslog_connection == 'static':
            for node_ip in all_node_ips:
                connect_map_dict[node_ip] = collector_ips[0]
        else:
            # Create a dictionary of connection mapping for remote clients to vizd servers based on round robin algorithm.
            # connect_map_dict = {<node-ip-address> : <collector-ip-address>}
            connect_map_dict = round_robin_collector_ip_assignment(
                all_node_ips,
                collector_ips)

        for host_string in args:
            #host_ip = host_string.split('@')[1]
            host_ip = hstr_to_ip(get_control_host_string(host_string))
            if host_ip == connect_map_dict[host_ip]:
                mode = 'receiver'
            else:
                mode = 'generator'

            with  settings(host_string=host_string):
                with cd(FAB_UTILS_DIR):
                    cmd = "python provision_rsyslog_connect.py "
                    myopts = "--rsyslog_port_number %s" % rsyslog_port
                    myopts += " --rsyslog_transport_protocol %s" % rsyslog_proto
                    myargs = myopts + " --mode %s" % mode
                    myargs += " --collector_ip %s" % connect_map_dict[host_ip]
                    run_cmd = cmd + myargs
                    sudo(run_cmd)

    elif env.rsyslog_params['status'].lower() == 'disable':
        # Call cleanup routine
        print "Cleaning up rsyslog configurations as env.rsyslog_params[status] is set to disable"
        execute('cleanup_remote_syslog')

    else:
        print "In env.rsyslog_params 'status' should be set to 'enable/disable' to setup/cleanup remote syslog."

    return True
# end setup_remote_syslog

@task
@EXECUTE_TASK
@hosts(get_tsn_nodes())
def setup_tsn():
    if get_tsn_nodes():
        execute('setup_tsn_node', env.host_string)

@task
def setup_tsn_node(*args):
    for host_string in args:
        # Frame the command line to provision tsn node.
        cmd = frame_vnc_compute_cmd(host_string,
                                    manage_nova_compute='no',
                                    configure_nova='no',
                                    cmd = 'setup-vnc-tsn')
        sudo(cmd)

@task
@EXECUTE_TASK
@roles('cfgm')
def create_toragent_haproxy():
    execute('create_toragent_haproxy_node', env.host_string)

def create_toragent_haproxy_node(*args):
    for host_string in args:
        for toragent_host in env.roledefs['toragent']:
            toragent_dict = getattr(env, 'tor_agent', None)
            if toragent_dict: 
                for i in range(len(toragent_dict[toragent_host])):
                    cmd = 'setup-vnc-toragent-haproxy'
                    cmd += ' --self_ip %s' % hstr_to_ip(get_control_host_string(toragent_host))
                    cmd += ' --torid %s' % toragent_dict[toragent_host][i]['tor_id']
                    cmd += ' --port %s' % toragent_dict[toragent_host][i]['tor_ovs_port']
                    cmd += ' --standby_ip %s' % toragent_dict[toragent_host][i]['standby_tor_agent_ip']
                    cmd += ' --standby_port %s' % toragent_dict[toragent_host][i]['standby_tor_agent_tor_ovs_port']
                    sudo(cmd)

@task
@EXECUTE_TASK
@hosts(get_toragent_nodes())
def setup_toragent(manage_nova_compute='yes', configure_nova='yes', restart='yes'):
    """Provisions vrouter/toragent services in all nodes defined in toragent role.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
       Even when we are no managing nova-compute (manage_nova_compute = no) still we execute few required config on
       nova.conf. If configure_nova = no; No nova config related configuration will executed on nova.conf file.
    """
    if get_toragent_nodes():
        execute('create_toragent_haproxy')
        manage_nova_compute = get_manage_nova_compute(manage_nova_compute)
        configure_nova = get_configure_nova(configure_nova)
        if get_orchestrator() == 'vcenter':
            manage_nova_compute='no'
            configure_nova='no'
        execute("setup_tor_agent_node",
                manage_nova_compute,
                configure_nova,
                restart,
                env.host_string)

@task
def provision_tor_agent_node(restart='no', *args):
    """Enable tor agent functionality in particular node. USAGE: fab add_tor_agent_node."""
    for host_string in args:
        with settings(host_string=host_string):
            # Frame the command line to provision compute node.
            cmd = frame_vnc_compute_cmd(host_string,
                                        manage_nova_compute='no',
                                        configure_nova='no')
            # Execute the provision compute script
            sudo(cmd)

            # Frame the command line to provision tsn node.
            toragent_dict = getattr(env,'tor_agent', None)
            for i in range(len(toragent_dict[host_string])):
                cmd = frame_vnc_toragent_cmd(host_string, torindex=i)
                # Execute the provision toragent script
                sudo(cmd)
	    # when we have HA configured for the agent, ensure that both
	    # TOR agents use same SSL certificates. Copy the created
	    # files to the corresponding HA node as well.
	    if ('standby_tor_agent_ip' in toragent_dict[host_string][i] and
	        'standby_tor_agent_tor_id' in toragent_dict[host_string][i]):
                host_string = [host for host in env.roledefs['all']\
                               if toragent_dict[host_string][i]['standby_tor_agent_ip'] ==\
                               hstr_to_ip(get_control_host_string(host))]
                if host_string:
                    ha_tor_id = str(toragent_dict[host_string][i]['standby_tor_agent_tor_id'])
                    cert_ha_file = '/etc/contrail/ssl/certs/tor.' + ha_tor_id + '.cert.pem'
                    priv_ha_file = '/etc/contrail/ssl/private/tor.' + ha_tor_id + '.privkey.pem'
                    temp_cert_file = tempfile.mktemp()
                    temp_priv_file = tempfile.mktemp()
                    get_as_sudo(cert_file, temp_cert_file)
                    get_as_sudo(privkey_file, temp_priv_file)
                    with settings(host_string=host_string[0]):
                        put(temp_cert_file, cert_ha_file, use_sudo=True)
                        put(temp_priv_file, priv_ha_file, use_sudo=True)
                    os.remove(temp_cert_file)
                    os.remove(temp_priv_file)

	    # if CA cert file is specified, copy it to the target
	    if ('ca_cert_file' in toragent_dict[host_string][i] and
		os.path.isfile(toragent_dict[host_string][i]['ca_cert_file'])):
		put(toragent_dict[host_string][i]['ca_cert_file'],
                    '/etc/contrail/ssl/certs/cacert.pem', use_sudo=True)

    if restart == 'yes':
	sudo("supervisorctl -c /etc/contrail/supervisord_vrouter.conf update")

@task
@hosts(env.roledefs['all'])
def cleanup_remote_syslog():
    """Cleans up all the configs needed for rsyslog on the server and the client side and restarts collector service
    and rsyslog clients. USAGE: fab cleanup_remote_syslog."""
    if env.roledefs['all']:
        execute("cleanup_remote_syslog_node", env.host_string)

@task
def cleanup_remote_syslog_node():
    """Cleans up all the configs needed for rsyslog on the server and the client side and restarts collector service
    and rsyslog clients in a node or list of nodes. USAGE: fab cleanup_remote_syslog:user@1.1.1.1,user@2.2.2.2"""
    default_port = 19876
    default_protocol = 'udp'

    for host_string in args:
        #host_ip = host_string.split('@')[1]
        host_ip = hstr_to_ip(get_control_host_string(host_string))
        mode = 'generator'
        collector_ips = role_to_ip_dict(role='collector')
        for each_collector in collector_ips:
            if host_ip == each_collector:
                mode = 'receiver'

        with  settings(host_string=host_string):
            with cd(FAB_UTILS_DIR):
                run_cmd = "python provision_rsyslog_connect.py --mode %s --cleanup True" \
                    % (mode)
                sudo(run_cmd)
# end cleanup_remote_syslog

@roles('build')
@task
def setup_orchestrator():
    orch = get_orchestrator()
    if orch == 'openstack':
        execute('setup_openstack')
        if get_openstack_internal_vip():
            execute('sync_keystone_ssl_certs')
            execute('setup_cluster_monitors')
        #execute('verify_openstack')
    #setup_vcenter can be called outside of setup_all and need not be below. So commenting.
    #elif orch == 'vcenter':
        #execute('setup_vcenter')

@roles('build')
@task
def setup_all(reboot='True'):
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute('setup_common')
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('setup_database')
    execute('fixup_mongodb_conf')
    execute('setup_mongodb_ceilometer_cluster')
    execute('setup_orchestrator') # openstack | vcenter
    execute('setup_cfgm')
    execute('setup_vcenter_plugin') # Will be executed only in case of vcenter orch
    execute('setup_control')
    execute('setup_collector')
    execute('setup_webui')
    execute('setup_vrouter')
    execute('setup_tsn')
    execute('setup_toragent')
    execute('prov_config_node')
    execute('prov_database_node')
    execute('prov_analytics_node')
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    execute('increase_vrouter_limit')
    if reboot == 'True':
        print "Rebooting the compute nodes after setup all."
        execute('compute_reboot')
        #Clear the connections cache
        connections.clear()
        execute('verify_compute')
    execute('setup_nova_aggregate')
#end setup_all

@roles('build')
@task
def setup_without_openstack(manage_nova_compute='yes', reboot='True'):
    """Provisions required contrail packages in all nodes as per the role definition except the openstack.
       User has to provision the openstack node with their custom openstack pakckages.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute will be skipped in the compute node.
    """
    execute('setup_common')
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('setup_database')
    execute('setup_cfgm')
    execute('setup_vcenter_plugin') # Will be executed only in case of vcenter orch
    execute('setup_control')
    execute('setup_collector')
    execute('setup_webui')
    execute('setup_vrouter', manage_nova_compute)
    execute('setup_tsn')
    execute('setup_toragent', manage_nova_compute)
    execute('prov_config_node')
    execute('prov_database_node')
    execute('prov_analytics_node')
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    execute('increase_vrouter_limit')
    if reboot == 'True':
        print "Rebooting the compute nodes after setup all."
        execute(compute_reboot)
        # Clear the connections cache
        connections.clear()
        execute('verify_compute')

@roles('build')
@task
def setup_contrail_analytics_components(manage_nova_compute='no', reboot='False'):
    """Provisions required contrail packages in all nodes as per the role definition.
       this task is used to provision non-networking contrail components, viz. database,
       config, analytics and webui
    """
    orch = getattr(env, 'orchestrator', None);
    if orch != 'none' and orch != None:
        raise RuntimeError("setup_contrail_analytics_components expects 'none' orchestrator (set to %s)" % orch)
    env.orchestrator = 'none'

    execute('setup_common')
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('setup_database')
    execute('setup_cfgm')
    execute('setup_collector')
    execute('setup_webui')
    execute('prov_config_node')
    execute('prov_database_node')
    execute('prov_analytics_node')
    execute('setup_remote_syslog')

@roles('build')
@task
def reimage_and_setup_test():
    execute(all_reimage)
    sleep(900)
    execute(setup_all)
    sleep(300)
    execute(setup_test_env)

@roles('build')
@task
def setup_all_with_images():
    execute('setup_all', reboot='False')
    execute('add_images')
    print "Rebooting the compute nodes after setup all."
    execute('compute_reboot')
    #Clear the connections cache
    connections.clear()
    execute('verify_compute')

@roles('build')
@task
def run_setup_demo():
    execute('setup_all', reboot='False')
    execute('config_demo')
    execute('add_images')
    print "Rebooting the compute nodes after setup all."
    execute('compute_reboot')
    #Clear the connections cache
    connections.clear()
    execute('verify_compute')
#end run_setup_demo

@task
@roles('build')
def setup_interface():
    '''
    Configure the IP address, netmask, gateway and vlan information
    based on parameter passed in 'control_data' stanza of testbed file.
    Also generate ifcfg file for the interface if the file is not present.
    '''
    execute('setup_interface_node')

@task
def setup_interface_node(*args):
    '''
    Configure the IP address, netmask, gateway and vlan information
    in one or list of nodes based on parameter passed to this task.
    '''
    hosts = getattr(testbed, 'control_data', None)
    if not hosts:
        print 'WARNING: \'control_data\' block is not defined in testbed file.',\
              'Skipping setup-interface...'
        return
    # setup interface for only the required nodes.
    if args:
        for host in args:
            if host not in hosts.keys():
                print "\n\n*** WARNING: control_data interface details for host " +\
                      "%s not defined in testbed file. Skipping! ***\n\n" % host
        hosts = dict((key, val) for (key, val) in
                     getattr(testbed, 'control_data', None).items()
                     if key in args)
    bondinfo = getattr(testbed, 'bond', None)

    retries = 5; timeout = 5
    for host in hosts.keys():
        cmd = 'setup-vnc-interfaces'
        errmsg = 'WARNING: Host ({HOST}) is defined with device ({DEVICE})'+\
                 ' but its bond info is not available\n'
        if hosts[host].has_key('device') and hosts[host].has_key('ip'):
            cmd += ' --device {device} --ip {ip}'.format(**hosts[host])
            device = hosts[host]['device']
            if 'bond' in device.lower():
                if not bondinfo or not (bondinfo.has_key(host)
                    and device == bondinfo[host]['name']):
                    print (errmsg.format(HOST=host,
                                           DEVICE=hosts[host]['device']))
                    continue
                if not bondinfo[host].has_key('member'):
                    raise AttributeError('Bond members are not defined for'+ \
                                         ' host %s, device %s' %(host, device))
                bond_members = " ".join(bondinfo[host]['member'])
                del bondinfo[host]['member']; del bondinfo[host]['name']
                cmd += ' --members %s --bond-opts \'%s\''%(bond_members,
                                             json.dumps(bondinfo[host]))
            if hosts[host].has_key('vlan'):
                cmd += ' --vlan %s' %hosts[host]['vlan']
            if (get_control_host_string(host) == host) and hosts[host].has_key('gw'):
                cmd += ' --gw %s' %hosts[host]['gw']
            with settings(host_string= host,
                          timeout= timeout,
                          connection_attempts= retries):
                with cd(INSTALLER_DIR):
                    sudo(cmd)
        else:
            raise AttributeError("'device' or 'ip' is not defined for %s" %host)
# end setup_interface

@roles('build')
@task
def reset_config():
    '''
    Reset api-server and openstack config and run the setup-scripts again incase you get into issues
    '''
    from fabfile.tasks.misc import run_cmd
    from fabfile.tasks.services import stop_cfgm, start_cfgm,\
          stop_database, start_database,\
          stop_contrail_control_services, restart_collector
    try:
        execute(stop_contrail_control_services)
        execute(cleanup_os_config)
        execute(setup_rabbitmq_cluster)
        execute(setup_database)
        execute(fixup_mongodb_conf)
        execute(setup_mongodb_ceilometer_cluster)
        execute(setup_orchestrator)
        execute(setup_cfgm)
        execute('setup_vcenter_plugin') # Will be executed only in case of vcenter orch
        execute(setup_control)
        execute(setup_collector)
        execute(setup_webui)
        execute(stop_database)
        execute(delete_cassandra_db_files)
        execute(start_database)
        execute(stop_cfgm)
        execute(config_server_reset, 'add', [env.roledefs['cfgm'][0]])
        execute(run_cmd, env.roledefs['cfgm'][0], "service supervisor-config restart")
        execute(start_cfgm)
        execute(restart_collector)
        sleep(120)
    except SystemExit:
        execute(config_server_reset, 'delete', [env.roledefs['cfgm'][0]])
        raise SystemExit("\nReset config Failed.... Aborting")
    else:
        execute(config_server_reset, 'delete', [env.roledefs['cfgm'][0]])
    sleep(60)
    execute(prov_database_node)
    execute(prov_analytics_node)
    execute(prov_control_bgp)
    execute(prov_external_bgp)
    execute(prov_metadata_services)
    execute(prov_encap_type)
    execute(setup_remote_syslog)
    execute(setup_vrouter)
    execute('setup_tsn')
    execute('setup_toragent', manage_nova_compute)
    execute('increase_vrouter_limit')
    execute(compute_reboot)
#end reset_config

@roles('build')
@task
def prov_esxi(*args):
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return
    orch =  get_orchestrator()
    if orch == 'vcenter':
        vcenter_info = getattr(env, 'vcenter', None)
        if not vcenter_info:
            print 'Info: vcenter block is not defined in testbed file.Exiting'
            return
    if args:
        host_list = args
    else:
        host_list = esxi_info.keys()

    std_switch = False
    dv_switch_fab = False
    power_on = False

    for host in host_list:
         with settings(host=host):
               if host in esxi_info.keys():
                   if orch == 'openstack':
                       std_switch = True
                   if orch == 'vcenter':
                       if 'dv_switch_fab' in vcenter_info.keys():
                           if not 'fabric_vswitch' in esxi_info[host].keys():
                               dv_switch_fab = True
                               std_switch = False
                           else:
                               std_switch = True
                       else:
                           std_switch = True
                   if (std_switch == True):
                       apply_esxi_defaults(esxi_info[host])
                       configure_esxi_network(esxi_info[host])
                       power_on = True
                   else:
                       apply_esxi_defaults(esxi_info[host])
                       esxi_info[host]['fabric_vswitch'] = None
                       power_on = False
                   if orch == 'openstack':
                       create_esxi_compute_vm(esxi_info[host], None, power_on)
                   if orch == 'vcenter':
                       create_esxi_compute_vm(esxi_info[host], vcenter_info, power_on)
               else:
                   print 'Info: esxi_hosts block does not have the esxi host.Exiting'

    if (dv_switch_fab == True):
         sleep(30)
         provision_dvs_fab(vcenter_info, esxi_info, host_list)
#end prov_compute_vm

@roles('build')
@task
def add_esxi_to_vcenter(*args):
    vcenter_info = getattr(env, 'vcenter', None)
    if not vcenter_info:
        print 'Error: vcenter block is not defined in testbed file.Exiting'
        return
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Error: esxi_hosts block is not defined in testbed file.Exiting'
        return
    if args:
        host_list = args
    else:
        host_list = esxi_info.keys()
    (hosts, clusters, vms) = get_esxi_vms_and_hosts(esxi_info, vcenter_info, host_list)
    provision_vcenter(vcenter_info, hosts, clusters, vms, 'True')

@roles('build')
@task
def setup_vcenter():
    vcenter_info = getattr(env, 'vcenter', None)
    if not vcenter_info:
        print 'Error: vcenter block is not defined in testbed file.Exiting'
        return
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Error: esxi_hosts block is not defined in testbed file.Exiting'
        return
    host_list = esxi_info.keys()
    (hosts, clusters, vms) = get_esxi_vms_and_hosts(esxi_info, vcenter_info, host_list)
    provision_vcenter(vcenter_info, hosts, clusters, vms, 'False')

@task
@roles('build')
def add_static_route():
    '''
    Add static route in the node based on parameter provided in the testbed file
    Sample configuration for testbed file
    static_route  = {
    host1 : [{ 'ip': '3.3.3.0', 'netmask' : '255.255.255.0', 'gw':'192.168.20.254', 'intf': 'p0p25p0' },
             { 'ip': '5.5.5.0', 'netmask' : '255.255.255.0', 'gw':'192.168.20.254', 'intf': 'p0p25p0' }],
    host3 : [{ 'ip': '4.4.4.0', 'netmask' : '255.255.255.0', 'gw':'192.168.20.254', 'intf': 'p6p0p1' }],
    }
    '''
    execute('add_static_route_node')

@task
def add_static_route_node(*args):
    '''
    Add static route in one or list of nodes based on parameter provided in the testbed file
    '''
    route_info = getattr(testbed, 'static_route', None)
    if not route_info:
        print 'WARNING: \'static_route\' block is not defined in testbed file.',\
              'Skipping add_static_route...'
        return
    # add static route for only the required nodes.
    if args:
        for host in args:
            if host not in route_info.keys():
                print "\n\n*** WARNING: static_route interface details for host " +\
                      "%s not defined in testbed file. Skipping! ***\n\n" % host
        route_info = dict((key, val) for (key, val) in
                     getattr(testbed, 'static_route', None).items()
                     if key in args)
    for tgt_host in route_info.keys():
        dest = ' --network'; gw = ' --gw'; netmask = ' --netmask'
        device = route_info[tgt_host][0]['intf']
        intf = ' --device %s' %device
        vlan = get_vlan_tag(device)
        for index in range(len(route_info[tgt_host])):
            dest += ' %s' %route_info[tgt_host][index]['ip']
            gw += ' %s' %route_info[tgt_host][index]['gw']
            netmask += ' %s' %route_info[tgt_host][index]['netmask']
        cmd = 'setup-vnc-static-routes' +\
                      dest + gw + netmask + intf
        if vlan:
            cmd += ' --vlan %s'%vlan
        with settings(host_string=tgt_host):
            with cd(INSTALLER_DIR):
                sudo(cmd)
# end add_static_route

@task
@roles('build')
def setup_network():
    '''
    Setup the underlay network based on parameters provided in the tested file
    '''
    execute('setup_network_node')

@task
def setup_network_node(*args):
    if args:
        execute('setup_interface_node', *args)
        execute('add_static_route_node', *args)
    else:
        execute('setup_interface_node')
        execute('add_static_route_node')
# end setup_network

def setup_esx_zone():
    """Provisions ESX servers into esx zone, if found in testbed."""
    esx = getattr(testbed, 'esxi_hosts', None)
    if esx is None:
        return
    sudo("(source /etc/contrail/openstackrc; nova aggregate-create esx esx)")
    cmd = "(source /etc/contrail/openstackrc; nova aggregate-add-host esx %s)"
    for server in esx:
        sudo(cmd % esx[server]['contrail_vm']['name'])
# end setup_esx_zone

@hosts(env.roledefs['openstack'][0:1])
@task
def setup_zones():
    """Setup availability zones."""
    setup_esx_zone()
#end setup_zones

@task
def increase_vrouter_limit():
    """Increase the maximum number of mpls label and nexthop on tsn node"""
    vrouter_module_params_dict = getattr(env, 'vrouter_module_params', None)
    if vrouter_module_params_dict:
        for host_string in vrouter_module_params_dict:
             cmd = "options vrouter"
             cmd += " vr_mpls_labels=%s" % vrouter_module_params_dict[host_string].setdefault('mpls_labels', '5120')
             cmd += " vr_nexthops=%s" % vrouter_module_params_dict[host_string].setdefault('nexthops', '65536')
             cmd += " vr_vrfs=%s" % vrouter_module_params_dict[host_string].setdefault('vrfs', '5120')
             cmd += " vr_bridge_entries=%s" % vrouter_module_params_dict[host_string].setdefault('macs', '262144')
             with settings(host_string=host_string, warn_only=True):
                 sudo("echo %s > %s" %(cmd, '/etc/modprobe.d/vrouter.conf'))

# end increase_vrouter_limit

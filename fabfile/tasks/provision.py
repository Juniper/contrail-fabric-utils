import string
import textwrap
import json
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
from fabfile.tasks.tester import setup_test_env
from fabfile.tasks.rabbitmq import setup_rabbitmq_cluster
from fabfile.tasks.vmware import provision_vcenter, provision_esxi_node,\
        configure_esxi_network, create_esxi_compute_vm
from fabfile.utils.cluster import get_vgw_details, get_orchestrator,\
        get_vmware_details
from fabfile.tasks.esxi_defaults import apply_esxi_defaults

FAB_UTILS_DIR = '/opt/contrail/utils/fabfile/utils/'

@task
@EXECUTE_TASK
@roles('all')
def bash_autocomplete_systemd():
    host = env.host_string
    output = sudo('uname -a')
    if 'xen' in output or 'el6' in output or 'ubuntu' in output:
        pass
    else:
        #Assume Fedora
        sudo("echo 'source /etc/bash_completion.d/systemd-bash-completion.sh' >> ~/.bashrc")

@roles('cfgm')
@task
def setup_cfgm():
    """Provisions config services in all nodes defined in cfgm role."""
    if env.roledefs['cfgm']:
        execute("setup_cfgm_node", env.host_string)

def get_openstack_credentials():
    ks_admin_user = get_keystone_admin_user()
    ks_admin_password = get_keystone_admin_password()
    return ks_admin_user, ks_admin_password
# end get_openstack_credentials

def fixup_restart_haproxy_in_all_cfgm(nworkers):
    template = string.Template("""
global
        tune.maxrewrite 1024
#contrail-config-marker-start
listen contrail-config-stats :5937
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend quantum-server *:9696
    default_backend    quantum-server-backend

frontend  contrail-api *:8082
    default_backend    contrail-api-backend

frontend  contrail-discovery *:5998
    default_backend    contrail-discovery-backend

backend quantum-server-backend
    option nolinger
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9697 check

backend contrail-api-backend
    option nolinger
    balance     roundrobin
$__contrail_api_backend_servers__
    #server  10.84.14.2 10.84.14.2:9100 check
    #server  10.84.14.2 10.84.14.2:9101 check

backend contrail-discovery-backend
    option nolinger
    balance     roundrobin
$__contrail_disc_backend_servers__
    #server  10.84.14.2 10.84.14.2:9110 check
    #server  10.84.14.2 10.84.14.2:9111 check

$__rabbitmq_config__
#contrail-config-marker-end
""")

    q_listen_port = 9697
    q_server_lines = ''
    api_listen_port = 9100
    api_server_lines = ''
    disc_listen_port = 9110
    disc_server_lines = ''
    rabbitmq_config = """
listen  rabbitmq 0.0.0.0:5673
    mode tcp
    maxconn 10000
    balance roundrobin
    option tcpka
    option redispatch
    timeout client 48h
    timeout server 48h\n"""
    space = ' ' * 3
    for host_string in env.roledefs['cfgm']:
        server_index = env.roledefs['cfgm'].index(host_string) + 1
        host_ip = hstr_to_ip(get_control_host_string(host_string))
        q_server_lines = q_server_lines + \
        '    server %s %s:%s check inter 2000 rise 2 fall 3\n' \
                    %(host_ip, host_ip, str(q_listen_port))
        for i in range(nworkers):
            api_server_lines = api_server_lines + \
            '    server %s %s:%s check inter 2000 rise 2 fall 3\n' \
                        %(host_ip, host_ip, str(api_listen_port + i))
            disc_server_lines = disc_server_lines + \
            '    server %s %s:%s check inter 2000 rise 2 fall 3\n' \
                        %(host_ip, host_ip, str(disc_listen_port + i))
        rabbitmq_config +=\
            '%s server rabbit%s %s:5672 check inter 2000 rise 2 fall 3 weight 1 maxconn 500\n'\
             % (space, server_index, host_ip)

    if get_contrail_internal_vip() == get_openstack_internal_vip():
        # Openstack and cfgm are same nodes.
        # Dont add rabbitmq confing twice in haproxy, as setup_ha has added already.
        rabbitmq_config = ''

    for host_string in env.roledefs['cfgm']:
        haproxy_config = template.safe_substitute({
            '__contrail_quantum_servers__': q_server_lines,
            '__contrail_api_backend_servers__': api_server_lines,
            '__contrail_disc_backend_servers__': disc_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            '__rabbitmq_config__': rabbitmq_config,
            })

        with settings(host_string=host_string):
            # chop old settings including pesky default from pkg...
            tmp_fname = "/tmp/haproxy-%s-config" %(host_string)
            get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-config-marker-start/,/^#contrail-config-marker-end/d' %s" %(tmp_fname))
                local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(tmp_fname))
            # ...generate new ones
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(haproxy_config)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg", use_sudo=True)
            local("rm %s" %(tmp_fname))

        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            sudo("chkconfig haproxy on")
            sudo("service haproxy restart")

# end fixup_restart_haproxy_in_all_cfgm

def fixup_restart_haproxy_in_one_compute(compute_host_string):
    compute_haproxy_template = string.Template("""
#contrail-compute-marker-start
listen contrail-compute-stats :5938
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__contrail_disc_stanza__

$__contrail_quantum_stanza__

$__contrail_qpid_stanza__

$__contrail_glance_api_stanza__

#contrail-compute-marker-end
""")


    ds_stanza_template = string.Template("""
$__contrail_disc_frontend__

backend discovery-server-backend
    balance     roundrobin
$__contrail_disc_servers__
    #server  10.84.14.2 10.84.14.2:5998 check
""")

    q_stanza_template = string.Template("""
$__contrail_quantum_frontend__

backend quantum-server-backend
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9696 check
""")

    g_api_stanza_template = string.Template("""
$__contrail_glance_api_frontend__

backend glance-api-backend
    balance     roundrobin
$__contrail_glance_apis__
    #server  10.84.14.2 10.84.14.2:9292 check
""")

    ds_frontend = textwrap.dedent("""\
        frontend discovery-server 127.0.0.1:5998
            default_backend discovery-server-backend
        """)

    q_frontend = textwrap.dedent("""\
        frontend quantum-server 127.0.0.1:9696
            default_backend quantum-server-backend
        """)

    g_api_frontend = textwrap.dedent("""\
        frontend glance-api 127.0.0.1:9292
            default_backend glance-api-backend
        """)

    haproxy_config = ''

    # if this compute is also config, skip quantum and discovery
    # stanza as they would have been generated in config context
    ds_stanza = ''
    q_stanza = ''
    if compute_host_string not in env.roledefs['cfgm']:
        # generate discovery service stanza
        ds_server_lines = ''
        for config_host_string in env.roledefs['cfgm']:
            host_ip = hstr_to_ip(config_host_string)
            ds_server_lines = ds_server_lines + \
            '    server %s %s:5998 check\n' %(host_ip, host_ip)

            ds_stanza = ds_stanza_template.safe_substitute({
                '__contrail_disc_frontend__': ds_frontend,
                '__contrail_disc_servers__': ds_server_lines,
                })

        # generate  quantum stanza
        q_server_lines = ''
        for config_host_string in env.roledefs['cfgm']:
            host_ip = hstr_to_ip(config_host_string)
            q_server_lines = q_server_lines + \
            '    server %s %s:9696 check\n' %(host_ip, host_ip)

            q_stanza = q_stanza_template.safe_substitute({
                '__contrail_quantum_frontend__': q_frontend,
                '__contrail_quantum_servers__': q_server_lines,
                })

    # if this compute is also openstack, skip glance-api stanza
    # as that would have been generated in openstack context
    g_api_stanza = ''
    if compute_host_string not in env.roledefs['openstack']:
        # generate a glance-api stanza
        g_api_server_lines = ''
        for openstack_host_string in env.roledefs['openstack']:
            host_ip = hstr_to_ip(openstack_host_string)
            g_api_server_lines = g_api_server_lines + \
            '    server %s %s:9292 check\n' %(host_ip, host_ip)

            g_api_stanza = g_api_stanza_template.safe_substitute({
                '__contrail_glance_api_frontend__': g_api_frontend,
                '__contrail_glance_apis__': g_api_server_lines,
                })
            # HACK: for now only one openstack
            break

    with settings(host_string=compute_host_string):
        # chop old settings including pesky default from pkg...
        tmp_fname = "/tmp/haproxy-%s-compute" %(compute_host_string)
        get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
        with settings(warn_only=True):
            local("sed -i -e '/^#contrail-compute-marker-start/,/^#contrail-compute-marker-end/d' %s"\
                   %(tmp_fname))
            local("sed -i -e 's/*:5000/*:5001/' %s" %(tmp_fname))
            local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(tmp_fname))
        # ...generate new ones
        compute_haproxy = compute_haproxy_template.safe_substitute({
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            '__contrail_disc_stanza__': ds_stanza,
            '__contrail_quantum_stanza__': q_stanza,
            '__contrail_glance_api_stanza__': g_api_stanza,
            '__contrail_qpid_stanza__': '',
            })
        cfg_file = open(tmp_fname, 'a')
        cfg_file.write(compute_haproxy)
        cfg_file.close()
        put(tmp_fname, "/etc/haproxy/haproxy.cfg", use_sudo=True)
        local("rm %s" %(tmp_fname))

        # enable
        with settings(host_string=compute_host_string, warn_only=True):
            sudo("chkconfig haproxy on")
            sudo("service haproxy restart")

# end fixup_restart_haproxy_in_one_compute

def fixup_restart_haproxy_in_all_compute():
    for compute_host_string in env.roledefs['compute']:
        fixup_restart_haproxy_in_one_compute(compute_host_string)

# end fixup_restart_haproxy_in_all_compute

def  fixup_restart_haproxy_in_all_openstack():
    openstack_haproxy_template = string.Template("""
#contrail-openstack-marker-start
listen contrail-openstack-stats :5936
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__contrail_quantum_stanza__

#contrail-openstack-marker-end
""")

    q_stanza_template = string.Template("""
$__contrail_quantum_frontend__

backend quantum-server-backend
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9696 check
""")

    q_frontend = textwrap.dedent("""\
        frontend quantum-server 127.0.0.1:9696
            default_backend quantum-server-backend
        """)

    # for all openstack, set appropriate haproxy stanzas
    for openstack_host_string in env.roledefs['openstack']:
        haproxy_config = ''

        # if this openstack is also config, skip quantum stanza
        # as that would have been generated in config context
        q_stanza = ''
        if openstack_host_string not in env.roledefs['cfgm']:
            # generate a quantum stanza
            q_server_lines = ''
            for config_host_string in env.roledefs['cfgm']:
                host_ip = hstr_to_ip(config_host_string)
                q_server_lines = q_server_lines + \
                '    server %s %s:9696 check\n' %(host_ip, host_ip)

                q_stanza = q_stanza_template.safe_substitute({
                    '__contrail_quantum_frontend__': q_frontend,
                    '__contrail_quantum_servers__': q_server_lines,
                    })

        with settings(host_string=openstack_host_string):
            # chop old settings including pesky default from pkg...
            tmp_fname = "/tmp/haproxy-%s-openstack" %(openstack_host_string)
            get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-openstack-marker-start/,/^#contrail-openstack-marker-end/d' %s"\
                       %(tmp_fname))
                local("sed -i -e 's/*:5000/*:5001/' %s" %(tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(tmp_fname))
            # ...generate new ones
            openstack_haproxy = openstack_haproxy_template.safe_substitute({
                '__contrail_hap_user__': 'haproxy',
                '__contrail_hap_passwd__': 'contrail123',
                '__contrail_quantum_stanza__': q_stanza,
                })
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(openstack_haproxy)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg", use_sudo=True)
            local("rm %s" %(tmp_fname))

            # enable
            with settings(host_string=openstack_host_string, warn_only=True):
                sudo("chkconfig haproxy on")
                sudo("service haproxy restart")

# end fixup_restart_haproxy_in_all_openstack

@task
def setup_cfgm_node(*args):
    """Provisions config services in one or list of nodes. USAGE: fab setup_cfgm_node:user@1.1.1.1,user@2.2.2.2"""

    nworkers = 1
    quantum_port = '9697'

    for host_string in args:
        # Enable settings for Ubuntu
        with  settings(host_string=host_string):
            enable_haproxy()
    fixup_restart_haproxy_in_all_cfgm(nworkers)

    for host_string in args:
        cfgm_host=get_control_host_string(host_string)
        tgt_ip = hstr_to_ip(cfgm_host)
        cfgm_host_password = env.passwords[host_string]

        # Prefer local collector node
        cfgm_host_list = [get_control_host_string(entry)\
                         for entry in env.roledefs['cfgm']]
        collector_host_list = [get_control_host_string(entry)\
                              for entry in env.roledefs['collector']]
        if cfgm_host in collector_host_list:
            collector_ip = tgt_ip
        else:
            # Select based on index
            hindex = cfgm_host_list.index(cfgm_host)
            hindex = hindex % len(env.roledefs['collector'])
            collector_host = get_control_host_string(env.roledefs['collector'][hindex])
            collector_ip = hstr_to_ip(collector_host)
        mt_opt = '--multi_tenancy' if get_mt_enable() else ''
        cassandra_ip_list = [hstr_to_ip(get_control_host_string(cassandra_host)) for cassandra_host in env.roledefs['database']]
        amqp_server_ip = get_contrail_amqp_server()
        orch = get_orchestrator()
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-config.override')
                    sudo('rm /etc/init/neutron-server.override')

            # Frame the command line to provision config node
            cmd = "setup-vnc-config"
            cmd += " --self_ip %s" % tgt_ip
            cmd += " --collector_ip %s %s" % (collector_ip, mt_opt)
            cmd += " --cassandra_ip_list %s" % ' '.join(cassandra_ip_list)
            cmd += " --zookeeper_ip_list %s" % ' '.join(cassandra_ip_list)
            cmd += " --quantum_port %s" % quantum_port
            cmd += " --nworkers %d" % nworkers
            cmd += " --service_token %s" % get_service_token()
            cmd += " --amqp_server_ip %s" % amqp_server_ip
            cmd += " --orchestrator %s" % orch
            haproxy = get_haproxy()
            if haproxy:
                cmd += " --haproxy %s" % haproxy
            if orch == 'openstack':
                openstack_admin_password = get_keystone_admin_password()
                keystone_ip = get_keystone_ip()
                # Pass keystone arguments in case for openstack orchestrator
                cmd += " --keystone_ip %s" % keystone_ip
                cmd += " --keystone_admin_passwd %s" % openstack_admin_password
                cmd += " --keystone_service_tenant_name %s" % get_keystone_service_tenant_name()
                cmd += " --keystone_auth_protocol %s" % get_keystone_auth_protocol()
                cmd += " --keystone_auth_port %s" % get_keystone_auth_port()
                cmd += " --keystone_admin_token %s" % get_keystone_admin_token()
                cmd += " --keystone_insecure %s" % get_keystone_insecure_flag()
                cmd += " --region_name %s" % get_region_name()
                manage_neutron = get_manage_neutron()
                if manage_neutron == 'no':
                    # Skip creating neutron service tenant/user/role etc in keystone.
                    cmd += ' --manage_neutron %s' % manage_neutron
            else:
                cmd += ' --manage_neutron no'
            internal_vip = get_contrail_internal_vip()
            if internal_vip:
                # Highly available setup
                cmd += ' --internal_vip %s' % (internal_vip)

            # Execute the provision config script
            with cd(INSTALLER_DIR):
                sudo(cmd)

            # Frame the command  to provision vcenter-plugin
            vcenter_info = getattr(env, 'vcenter', None)
            if not vcenter_info:
                print 'Error: vcenter block is not defined in testbed file.Exiting'
                return
            cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))

            if orch == 'vcenter':
                cmd = "setup-vcenter-plugin"
                cmd += " --vcenter_url %s" % vcenter_info['server']
                cmd += " --vcenter_username %s" % vcenter_info['username']
                cmd += " --vcenter_password %s" % vcenter_info['password']
                cmd += " --vcenter_datacenter %s" % vcenter_info['datacenter']
                cmd += " --vcenter_dvswitch %s" % vcenter_info['dv_switch']['dv_switch_name']
                cmd += " --api_hostname %s" % cfgm_ip
                cmd += " --api_port 8082"
                zk_servers_ports = ','.join(['%s:2181' %(s) for s in cassandra_ip_list])
                cmd += " --zookeeper_serverlist %s" % zk_servers_ports

            # Execute the provision vcenter-plugin script
            with cd(INSTALLER_DIR):
                sudo(cmd)


    # HAPROXY fixups
    haproxy = get_haproxy_opt()
    if haproxy:
        fixup_restart_haproxy_in_all_compute()
        fixup_restart_haproxy_in_all_openstack()
#end setup_cfgm_node

@task
@roles('compute')
def setup_ceilometer_compute():
    """Provisions ceilometer compute services in all nodes defined in compute role."""
    if env.roledefs['compute']:
        execute("setup_ceilometer_compute_node", env.host_string)

@task
def setup_ceilometer_compute_node(*args):
    """Provisions ceilometer compute services in one or list of nodes. USAGE: fab setup_ceilometer_compute_node:user@1.1.1.1,user@2.2.2.2"""
    amqp_server_ip = get_openstack_amqp_server()
    openstack_host = get_control_host_string(env.roledefs['openstack'][0])
    openstack_ip = hstr_to_ip(openstack_host)
    for host_string in args:
        with  settings(host_string=host_string):
            with settings(warn_only=True):
                compute_ceilometer_present = sudo("grep '^instance_usage_audit =' /etc/nova/nova.conf").succeeded
            if not compute_ceilometer_present:
                config_cmd = "openstack-config --set /etc/nova/nova.conf DEFAULT"
                sudo("%s notification_driver ceilometer.compute.nova_notifier" % config_cmd)
                sudo("%s notification_driver nova.openstack.common.notifier.rpc_notifier" % config_cmd)
                sudo("%s notify_on_state_change vm_and_task_state" % config_cmd)
                sudo("%s instance_usage_audit_period hour" % config_cmd)
                sudo("%s instance_usage_audit True" % config_cmd)
                sudo("service nova-compute restart")

            if host_string != openstack_host:
                #ceilometer.conf updates
                conf_file = "/etc/ceilometer/ceilometer.conf"
                sudo("openstack-config --set %s DEFAULT rabbit_host %s" % (conf_file, amqp_server_ip))
                value = "/var/log/ceilometer"
                sudo("openstack-config --set %s DEFAULT log_dir %s" % (conf_file, value))
                value = "a74ca26452848001921c"
                sudo("openstack-config --set %s DEFAULT metering_secret %s" % (conf_file, value))
                sudo("openstack-config --set %s DEFAULT auth_strategy keystone" % conf_file)
                with settings(warn_only=True):
                    authtoken_config = sudo("grep '^auth_host =' /etc/ceilometer/ceilometer.conf").succeeded
                if not authtoken_config:
                    config_cmd = "openstack-config --set %s keystone_authtoken" % conf_file
                    sudo("%s admin_password CEILOMETER_PASS" % config_cmd)
                    sudo("%s admin_user ceilometer" % config_cmd)
                    sudo("%s admin_tenant_name service" % config_cmd)
                    sudo("%s auth_uri http://%s:5000" % (config_cmd, openstack_ip))
                    sudo("%s auth_protocol http" % config_cmd)
                    sudo("%s auth_port 35357" % config_cmd)
                    sudo("%s auth_host %s" % (config_cmd, openstack_ip))
                    config_cmd = "openstack-config --set %s service_credentials" % conf_file
                    sudo("%s os_password CEILOMETER_PASS" % config_cmd)
                    sudo("%s os_tenant_name service" % config_cmd)
                    sudo("%s os_username ceilometer" % config_cmd)
                    sudo("%s os_auth_url http://%s:5000/v2.0" % (config_cmd, openstack_ip))

            sudo("service ceilometer-agent-compute restart")

@task
@roles('openstack')
def setup_ceilometer():
    """Provisions ceilometer services in all nodes defined in openstack role."""
    if env.roledefs['openstack'] and env.host_string == env.roledefs['openstack'][0]:
        execute("setup_ceilometer_node", env.host_string)

    execute("setup_image_service_node", env.host_string)

@task
def setup_ceilometer_node(*args):
    """Provisions ceilometer services in one or list of nodes. USAGE: fab setup_ceilometer_node:user@1.1.1.1,user@2.2.2.2"""
    amqp_server_ip = get_openstack_amqp_server()
    for host_string in args:
        self_host = get_control_host_string(host_string)
        self_ip = hstr_to_ip(self_host)

        with  settings(host_string=host_string):

            output = sudo("dpkg-query --show nova-api")
            if output.find('2013.2') != -1:
                openstack_sku = 'havana'
            elif output.find('2014.1') != -1:
                openstack_sku = 'icehouse'
            else:
                print "setup_ceilometer_node: openstack dist unknown.. assuming icehouse.."
                openstack_sku = 'icehouse'

            if openstack_sku == 'havana':
                ceilometer_services = ['ceilometer-agent-central',
                                       'ceilometer-api',
                                       'ceilometer-collector']
            else:
                ceilometer_services = ['ceilometer-agent-central',
                                       'ceilometer-agent-notification',
                                       'ceilometer-api',
                                       'ceilometer-collector',
                                       'ceilometer-alarm-evaluator',
                                       'ceilometer-alarm-notifier']
            with settings(warn_only=True):
                cmd = "mongo --host " + self_ip + " --eval 'db = db.getSiblingDB(\"ceilometer\"); db.addUser({user: \"ceilometer\", pwd: \"CEILOMETER_DBPASS\", roles: [ \"readWrite\", \"dbAdmin\" ]})'"
                sudo(cmd);

            conf_file = "/etc/ceilometer/ceilometer.conf"
            value = "mongodb://ceilometer:CEILOMETER_DBPASS@" + self_ip + ":27017/ceilometer"
            sudo("openstack-config --set %s DEFAULT connection %s" % (conf_file, value))
            sudo("openstack-config --set %s DEFAULT rabbit_host %s" % (conf_file, amqp_server_ip))
            value = "/var/log/ceilometer"
            sudo("openstack-config --set %s DEFAULT log_dir %s" % (conf_file, value))
            value = "a74ca26452848001921c"
            sudo("openstack-config --set %s DEFAULT metering_secret %s" % (conf_file, value))
            sudo("openstack-config --set %s DEFAULT auth_strategy keystone" % conf_file)
            #keystone auth params
            with settings(warn_only=True):
                ceilometer_user_exists = sudo("source /etc/contrail/openstackrc;keystone user-list | grep ceilometer").succeeded
            if not ceilometer_user_exists:
                sudo("source /etc/contrail/openstackrc;keystone user-create --name=ceilometer --pass=CEILOMETER_PASS --tenant=service --email=ceilometer@example.com")
                sudo("source /etc/contrail/openstackrc;keystone user-role-add --user=ceilometer --tenant=service --role=admin")

            with settings(warn_only=True):
                authtoken_config = sudo("grep '^auth_host =' /etc/ceilometer/ceilometer.conf").succeeded
            if not authtoken_config:
                config_cmd = "openstack-config --set %s keystone_authtoken" % conf_file
                sudo("%s admin_password CEILOMETER_PASS" % config_cmd)
                sudo("%s admin_user ceilometer" % config_cmd)
                sudo("%s admin_tenant_name service" % config_cmd)
                sudo("%s auth_uri http://%s:5000" % (config_cmd, self_ip))
                sudo("%s auth_protocol http" % config_cmd)
                sudo("%s auth_port 35357" % config_cmd)
                sudo("%s auth_host %s" % (config_cmd, self_ip))
                config_cmd = "openstack-config --set %s service_credentials" % conf_file
                sudo("%s os_password CEILOMETER_PASS" % config_cmd)
                sudo("%s os_tenant_name service" % config_cmd)
                sudo("%s os_username ceilometer" % config_cmd)
                sudo("%s os_auth_url http://%s:5000/v2.0" % (config_cmd, self_ip))

            #create keystone service and endpoint
            with settings(warn_only=True):
                ceilometer_service_exists = sudo("source /etc/contrail/openstackrc;keystone service-list | grep ceilometer").succeeded
            if not ceilometer_service_exists:
                sudo("source /etc/contrail/openstackrc;keystone service-create --name=ceilometer --type=metering --description=\"Telemetry\"")
                sudo("source /etc/contrail/openstackrc;keystone endpoint-create --service-id=$(keystone service-list | awk '/ metering / {print $2}') --publicurl=http://%s:8777 --internalurl=http://%s:8777 --adminurl=http://%s:8777" %(self_ip, self_ip, self_ip))
            for svc in ceilometer_services:
                sudo("service %s restart" %(svc))
#end setup_ceilometer_node

@task
def setup_image_service_node(*args):
    """Provisions image services in one or list of nodes. USAGE: fab setup_image_service_node:user@1.1.1.1,user@2.2.2.2"""
    amqp_server_ip = get_openstack_amqp_server()
    for host_string in args:
        output = sudo("dpkg-query --show nova-api")
        if output.find('2013.2') != -1:
            openstack_sku = 'havana'
        elif output.find('2014.1') != -1:
            openstack_sku = 'icehouse'
        else:
            print "setup_image_service_node: openstack dist unknown.. assuming icehouse.."
            openstack_sku = 'icehouse'

        glance_configs = {'DEFAULT' : {'notification_driver' : 'messaging',
                                       'rpc_backend' : 'rabbit',
                                       'rabbit_host' : '%s' % amqp_server_ip,
                                       'rabbit_password' : 'guest'}
                        }
        if openstack_sku == 'havana':
            glance_configs['DEFAULT']['notifier_strategy'] = 'rabbit'
            glance_configs['DEFAULT']['rabbit_userid'] = 'guest'

        conf_file = "/etc/glance/glance-api.conf"
        for section, key_values in glance_configs:
            for key, value in key_values:
                sudo("openstack-config --set %s %s %s" % (conf_file, section, key, value))
        sudo("service glance-registry restart")
        sudo("service glance-api restart")

@task
@roles('openstack')
def setup_openstack():
    """Provisions openstack services in all nodes defined in openstack role."""
    execute('add_openstack_reserverd_ports')
    if env.roledefs['openstack']:
        execute("setup_openstack_node", env.host_string)
        # Blindly run setup_openstack twice for Ubuntu
        #TODO Need to remove this finally
        if detect_ostype() == 'ubuntu':
            execute("setup_openstack_node", env.host_string)
        if is_package_installed('contrail-openstack-dashboard'):
            execute('setup_contrail_horizon_node', env.host_string)

@roles('openstack')
@task
def setup_contrail_horizon():
    if env.roledefs['openstack']:
        if is_package_installed('contrail-openstack-dashboard'):
            execute('setup_contrail_horizon_node', env.host_string)

@task
def setup_openstack_node(*args):
    """Provisions openstack services in one or list of nodes. USAGE: fab setup_openstack_node:user@1.1.1.1,user@2.2.2.2"""
    #qpidd_changes_for_ubuntu()

    amqp_server_ip = get_openstack_amqp_server()
    for host_string in args:
        openstack_ip_list = []
        self_host = get_control_host_string(host_string)
        self_ip = hstr_to_ip(self_host)
        mgmt_self_ip = hstr_to_ip(host_string)
        openstack_host_password = env.passwords[host_string]
        keystone_ip = get_keystone_ip(ignore_vip=True, openstack_node=env.host_string)
        openstack_admin_password = get_keystone_admin_password()
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_ip = hstr_to_ip(cfgm_host)
        internal_vip = get_openstack_internal_vip()

        # Frame the command line to provision openstack
        cmd = "setup-vnc-openstack"
        cmd += " --self_ip %s" % self_ip
        cmd += " --keystone_ip %s" % keystone_ip
        cmd += " --keystone_admin_passwd %s" % openstack_admin_password
        cmd += " --cfgm_ip %s " % cfgm_ip
        cmd += " --keystone_auth_protocol %s" % get_keystone_auth_protocol()
        cmd += " --amqp_server_ip %s" % amqp_server_ip
        cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
        cmd += " --service_token %s" % get_service_token()
        cmd += ' --openstack_index %s' % (env.roledefs['openstack'].index(host_string) + 1)
        haproxy = get_haproxy()
        if haproxy:
            cmd += " --haproxy %s" % haproxy
        if internal_vip:
            # Highly available setup
            openstack_ip_list = ' '.join([hstr_to_ip(openstack_host) for openstack_host in env.roledefs['openstack']])
            cmd += ' --internal_vip %s' % (internal_vip)
            cmd += ' --mgmt_self_ip %s' % mgmt_self_ip
        contrail_internal_vip = get_contrail_internal_vip()
        if contrail_internal_vip:
            # Highly available setup with multiple interface
            cmd += ' --contrail_internal_vip %s' % (contrail_internal_vip)
        if openstack_ip_list:
            cmd += ' --openstack_ip_list %s' % openstack_ip_list

        # Execute the provision openstack script
        with  settings(host_string=host_string):
            with cd(INSTALLER_DIR):
                sudo(cmd)
#end setup_openstack_node

@task
def setup_contrail_horizon_node(*args):
    '''
    Configure horizon to pick up contrail customization
    Based on OS and SKU type pick conf file in following order:
    1. /etc/openstack-dashboard/local_settings.py
    2. /etc/openstack-dashboard/local_settings
    3. /usr/lib/python2.6/site-packages/openstack_dashboard/local/local_settings.py
    '''
    file_name = '/etc/openstack-dashboard/local_settings.py'
    if not exists(file_name):
        file_name = '/etc/openstack-dashboard/local_settings'
    if not exists(file_name):
        file_name = '/usr/lib/python2.6/site-packages/openstack_dashboard/local/local_settings.py'
    if not exists(file_name):
        return

    pattern='^HORIZON_CONFIG.*customization_module.*'
    line = '''HORIZON_CONFIG[\'customization_module\'] = \'contrail_openstack_dashboard.overrides\' '''
    insert_line_to_file(pattern = pattern, line = line, file_name = file_name)

    pattern = 'LOGOUT_URL.*'
    if detect_ostype() == 'ubuntu':
        line = '''LOGOUT_URL='/horizon/auth/logout/' '''
        web_restart = 'service apache2 restart'
    else:
        line = '''LOGOUT_URL='/dashboard/auth/logout/' '''
        web_restart = 'service httpd restart'

    insert_line_to_file(pattern = pattern, line = line, file_name = file_name)

    #HA settings
    internal_vip = get_openstack_internal_vip()
    if internal_vip:
        with settings(warn_only=True):
            hash_key = sudo("grep 'def hash_key' %s" % file_name).succeeded
        if not hash_key:
            # Add a hash generating function
            sudo('sed -i "/^SECRET_KEY.*/a\    return new_key" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\        new_key = m.hexdigest()" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\        m.update(new_key)" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\        m = hashlib.md5()" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\    if len(new_key) > 250:" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\    new_key = \':\'.join([key_prefix, str(version), key])" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\def hash_key(key, key_prefix, version):" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\import hashlib" %s' % file_name)
            sudo('sed -i "/^SECRET_KEY.*/a\# To ensure key size of 250" %s' % file_name)
        sudo("sed  -i \"s/'LOCATION' : '127.0.0.1:11211',/'LOCATION' : '%s:11211',/\" %s" % (hstr_to_ip(env.host_string), file_name))
        with settings(warn_only=True):
            if sudo("grep '\'KEY_FUNCTION\': hash_key,' %s" % file_name).failed:
                sudo('sed -i "/\'LOCATION\'.*/a\       \'KEY_FUNCTION\': hash_key," %s' % file_name)
        sudo("sed -i -e 's/OPENSTACK_HOST = \"127.0.0.1\"/OPENSTACK_HOST = \"%s\"/' %s" % (internal_vip,file_name))

    sudo(web_restart)
#end setup_contrail_horizon_node

@task
@roles('collector')
def setup_collector():
    """Provisions collector services in all nodes defined in collector role."""
    if env.roledefs['collector']:
        execute("setup_collector_node", env.host_string)

@task
def setup_collector_node(*args):
    """Provisions collector services in one or list of nodes. USAGE: fab setup_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        #we need the redis to be listening on *, comment bind line
        with  settings(host_string=host_string):
            with settings(warn_only=True):
                if detect_ostype() == 'ubuntu':
                    run("service redis-server stop")
                    run("sed -i -e '/^[ ]*bind/s/^/#/' /etc/redis/redis.conf")
                    run("service redis-server start")
                    #check if the redis-server is running, if not, issue start again
                    count = 1
                    while run("service redis-server status | grep not").succeeded:
                        count += 1
                        if count > 10:
                            break
                        sleep(1)
                        run("service redis-server restart")
                else:
                    sudo("service redis stop")
                    sudo("sed -i -e '/^[ ]*bind/s/^/#/' /etc/redis.conf")
                    sudo("chkconfig redis on")
                    sudo("service redis start")

        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        collector_host_password = env.passwords[host_string]
        collector_host = get_control_host_string(host_string)
        ncollectors = len(env.roledefs['collector'])
        redis_master_host = get_control_host_string(env.roledefs['collector'][0])
        if collector_host == redis_master_host:
            is_redis_master = True
        else:
            is_redis_master = False
        tgt_ip = hstr_to_ip(collector_host)
        cassandra_host_list = [get_control_host_string(cassandra_host) for cassandra_host in env.roledefs['database']]
        if collector_host in cassandra_host_list:
            cassandra_host_list.remove(collector_host)
            cassandra_host_list.insert(0, collector_host)
        cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in cassandra_host_list]
        redis_master_ip = hstr_to_ip(redis_master_host)

        # Frame the command line to provision collector
        cmd = "setup-vnc-collector"
        cmd += " --cassandra_ip_list %s" % (' '.join(cassandra_ip_list))
        cmd += " --cfgm_ip %s" % cfgm_ip
        cmd += " --self_collector_ip %s" % tgt_ip
        cmd += " --num_nodes %d " % ncollectors
        analytics_syslog_port = get_collector_syslog_port()
        if analytics_syslog_port is not None:
            cmd += "--analytics_syslog_port %d " % analytics_syslog_port
        analytics_database_ttl = get_database_ttl()
        if analytics_database_ttl is not None:
            cmd += "--analytics_data_ttl %d " % analytics_database_ttl
        else:
            #if nothing is provided we default to 48h
            cmd += "--analytics_data_ttl 48 "
        analytics_config_audit_ttl = get_analytics_config_audit_ttl()
        if analytics_config_audit_ttl is not None:
            cmd += "--analytics_config_audit_ttl %d " % analytics_config_audit_ttl
        else:
            cmd += "--analytics_config_audit_ttl -1 "
        analytics_statistics_ttl = get_analytics_statistics_ttl()
        if analytics_statistics_ttl is not None:
            cmd += "--analytics_statistics_ttl %d " % analytics_statistics_ttl
        else:
            cmd += "--analytics_statistics_ttl -1 "
        analytics_flow_ttl = get_analytics_flow_ttl()
        if analytics_flow_ttl is not None:
            cmd += "--analytics_flow_ttl %d " % analytics_flow_ttl
        else:
            cmd += "--analytics_flow_ttl -1 "

        internal_vip = get_contrail_internal_vip()
        if internal_vip:
            # Highly Available setup
            cmd += " --internal_vip %s" % internal_vip

        # Execute the provision collector script
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-analytics.override')
            with cd(INSTALLER_DIR):
                print cmd
                sudo(cmd)
#end setup_collector

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
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        database_host = host_string
        database_host_list = [get_control_host_string(entry) for entry in env.roledefs['database']]
        database_ip_list = [hstr_to_ip(db_host) for db_host in database_host_list]
        database_host=get_control_host_string(host_string)
        database_host_password=env.passwords[host_string]
        tgt_ip = hstr_to_ip(database_host)

        # Frame the command line to provision database
        cmd = "setup-vnc-database"
        cmd += " --self_ip %s" % tgt_ip
        cmd += " --cfgm_ip %s" % cfgm_ip
        database_dir = get_database_dir()
        if database_dir is not None:
            cmd += " --data_dir %s" % database_dir
        analytics_data_dir = get_analytics_data_dir()
        if analytics_data_dir is not None:
            cmd += " --analytics_data_dir %s" % analytics_data_dir
        ssd_data_dir = get_ssd_data_dir()
        if ssd_data_dir is not None:
            cmd += " --ssd_data_dir %s" % ssd_data_dir
        if (len(env.roledefs['database'])>2):
            cmd += " --seed_list %s" % ','.join(database_ip_list[:2])
        else:
            cmd += " --seed_list %s" % (hstr_to_ip(get_control_host_string(env.roledefs['database'][0])))
        cmd += " --zookeeper_ip_list %s" % ' '.join(database_ip_list)
        cmd += " --database_index %d" % (database_host_list.index(database_host) + 1)

        # Execute the provision database script
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-database.override')
            with cd(INSTALLER_DIR):
                sudo(cmd)
#end setup_database

@task
@roles('webui')
def setup_webui():
    """Provisions webui services in all nodes defined in webui role."""
    if env.roledefs['webui']:
        execute("setup_webui_node", env.host_string)

@task
def setup_webui_node(*args):
    """Provisions webui services in one or list of nodes. USAGE: fab setup_webui_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_ip = hstr_to_ip(cfgm_host)
        webui_host = get_control_host_string(host_string)
        cfgm_host_password=env.passwords[host_string]
        ncollectors = len(env.roledefs['collector'])
        database_host_list=[]
        for entry in env.roledefs['database']:
            database_host_list.append(get_control_host_string(entry))
        webui_host_list=[]
        for entry in env.roledefs['webui']:
            webui_host_list.append(get_control_host_string(entry))
        # Prefer local collector node
        if webui_host in env.roledefs['collector']:
            collector_ip = hstr_to_ip(webui_host)
        else:
            # Select based on index
            hindex = webui_host_list.index(webui_host)
            hindex = hindex % ncollectors
            collector_host = get_control_host_string(env.roledefs['collector'][hindex])
            collector_ip = hstr_to_ip(collector_host)
        cassandra_ip_list = [hstr_to_ip(cassandra_host) for cassandra_host in database_host_list]
        orch = get_orchestrator()

        # Frame the command line to provision webui
        cmd = "setup-vnc-webui"
        cmd += " --cfgm_ip %s" % cfgm_ip
        cmd += " --collector_ip %s" % collector_ip
        cmd += " --cassandra_ip_list %s" % ' '.join(cassandra_ip_list)
        cmd += " --orchestrator %s" % orch
        internal_vip = get_openstack_internal_vip()
        if internal_vip:
            # Highly available setup
            cmd += " --internal_vip %s" % internal_vip
        contrail_internal_vip = get_contrail_internal_vip()
        if contrail_internal_vip:
            # Highly available setup with multiple interfaces
            cmd += " --contrail_internal_vip %s" % contrail_internal_vip

        if orch == 'openstack':
            openstack_host = get_control_host_string(env.roledefs['openstack'][0])
            openstack_ip = hstr_to_ip(openstack_host)
            keystone_ip = get_keystone_ip()
            ks_admin_user, ks_admin_password = get_openstack_credentials()
            cmd += " --keystone_ip %s" % keystone_ip
            cmd += " --openstack_ip %s" % openstack_ip
            cmd += " --admin_user %s" % ks_admin_user
            cmd += " --admin_password %s" % ks_admin_password
            cmd += " --admin_token %s" % get_keystone_admin_token()
            cmd += " --admin_tenant_name %s" % get_keystone_admin_tenant_name()
	elif orch == 'vcenter':
            vcenter_info = getattr(env, 'vcenter', None)
            if not vcenter_info:
                print 'Error: vcenter block is not defined in testbed file.Exiting'
                return
            # vcenter provisioning parameters
            cmd += " --vcenter_ip %s" % vcenter_info['server']
            cmd += " --vcenter_port %s" % vcenter_info['port']
            cmd += " --vcenter_auth %s" % vcenter_info['auth']
            cmd += " --vcenter_datacenter %s" % vcenter_info['datacenter']
            cmd += " --vcenter_dvswitch %s" % vcenter_info['dv_switch']['dv_switch_name']

        # Execute the provision webui script
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-webui.override')
            with cd(INSTALLER_DIR):
                sudo(cmd)
#end setup_webui

@task
@roles('control')
def setup_control():
    """Provisions control services in all nodes defined in control role."""
    if env.roledefs['control']:
        execute("setup_control_node", env.host_string)

def fixup_irond_config(control_host_string):
    control_ip = hstr_to_ip(get_control_host_string(control_host_string))
    for config_host_string in env.roledefs['cfgm']:
        with settings(host_string=config_host_string):
            pfl = "/etc/ifmap-server/basicauthusers.properties"
            # replace control-node and dns proc creds
            sudo("sed -i -e '/%s:/d' -e '/%s.dns:/d' %s" \
                      %(control_ip, control_ip, pfl))
            sudo("echo '%s:%s' >> %s" \
                         %(control_ip, control_ip, pfl))
            sudo("echo '%s.dns:%s.dns' >> %s" \
                         %(control_ip, control_ip, pfl))
# end fixup_irond_config

@task
def setup_control_node(*args):
    """Provisions control services in one or list of nodes. USAGE: fab setup_control_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        fixup_irond_config(host_string)
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password=env.passwords[env.roledefs['cfgm'][0]]
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        control_host = get_control_host_string(host_string)
        tgt_ip = hstr_to_ip(control_host)
        collector_host_list=[]
        for entry in env.roledefs['collector']:
            collector_host_list.append(get_control_host_string(entry))
        control_host_list=[]
        for entry in env.roledefs['control']:
            control_host_list.append(get_control_host_string(entry))
        # Prefer local collector node
        if control_host in collector_host_list:
            collector_ip = tgt_ip
        else:
            # Select based on index
            hindex = control_host_list.index(control_host)
            hindex = hindex % len(env.roledefs['collector'])
            collector_host = get_control_host_string(env.roledefs['collector'][hindex])
            collector_ip = hstr_to_ip(collector_host)
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-control.override')
                    sudo('rm /etc/init/supervisor-dns.override')
            with cd(INSTALLER_DIR):
                sudo("setup-vnc-control --self_ip %s --cfgm_ip %s --collector_ip %s" \
                     %(tgt_ip, cfgm_ip, collector_ip))
                if detect_ostype() == 'centos':
                    sudo("service contrail-control restart")
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
    if env.roledefs['compute']:
       # Launching of VM is not surrently supported in TSN node.
       # Not proviosning nova_compute incase the compute node is TSN.
       if 'tsn' in env.roledefs.keys():
           if  env.host_string in env.roledefs['tsn']:
               manage_nova_compute='no'
               configure_nova='no'
       execute("setup_only_vrouter_node", manage_nova_compute, configure_nova,  env.host_string)

@task
def setup_vrouter_node(*args):
    """Provisions nova-compute and vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute("setup_only_vrouter_node", 'yes', 'yes', *args)

@task
def setup_only_vrouter_node(manage_nova_compute='yes', configure_nova='yes', *args):
    """Provisions only vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
    """
    # make sure an agent pkg has been installed
    #try:
    #    sudo("yum list installed | grep contrail-agent")
    #except SystemExit as e:
    #    print "contrail-agent package not installed. Install it and then run setup_vrouter"
    #    return

    orch = get_orchestrator()
    if orch is 'openstack':
        # reset openstack connections to create new connections
        # when running in parallel mode
        openstack_host = env.roledefs['openstack'][0]
        openstack_host_connection = openstack_host + ':22'
        if connections and openstack_host_connection in connections.keys():
            connections.pop(openstack_host_connection)

        # Use metadata_secret provided in testbed. If not available
        # retrieve neutron_metadata_proxy_shared_secret from openstack
        metadata_secret = getattr(testbed,
                                  'neutron_metadata_proxy_shared_secret',
                                  None)
        if not metadata_secret:
            with settings(host_string=openstack_host):
                status, secret = get_value('/etc/nova/nova.conf',
                                     'DEFAULT',
                                     'service_neutron_metadata_proxy',
                                     'neutron_metadata_proxy_shared_secret')
            metadata_secret = secret if status == 'True' else None

    for host_string in args:
        # Enable haproxy for Ubuntu
        with  settings(host_string=host_string):
            enable_haproxy()
        #qpidd_changes_for_ubuntu()
        ncontrols = len(env.roledefs['control'])
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
        cfgm_passwd = env.passwords[env.roledefs['cfgm'][0]]
        compute_host = get_control_host_string(host_string)
        (tgt_ip, tgt_gw) = get_data_ip(host_string)

        compute_mgmt_ip= host_string.split('@')[1]
        compute_control_ip= hstr_to_ip(compute_host)

        haproxy = get_haproxy_opt()
        if haproxy:
            # setup haproxy and enable
            fixup_restart_haproxy_in_one_compute(host_string)

        amqp_server_ip = get_contrail_amqp_server()
        # Using amqp running in openstack node
        if (get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes' or
            get_from_testbed_dict('openstack', 'amqp_host', None)):
            amqp_server_ip = get_openstack_amqp_server()

        # Frame the command line to provision compute node.
        cmd = "setup-vnc-compute"
        cmd += " --self_ip %s" % compute_control_ip
        cmd += " --cfgm_ip %s" % cfgm_ip
        cmd += " --cfgm_user %s" % cfgm_user
        cmd += " --cfgm_passwd %s" % cfgm_passwd
        cmd += " --ncontrols %s" % ncontrols
        cmd += " --amqp_server_ip %s" % amqp_server_ip
        cmd += " --service_token %s" % get_service_token()
        cmd += " --orchestrator %s" % get_orchestrator()
        haproxy = get_haproxy()
        if haproxy:
            cmd += " --haproxy %s" % haproxy
        if tgt_ip != compute_mgmt_ip:
            cmd += " --non_mgmt_ip %s" % tgt_ip
            cmd += " --non_mgmt_gw %s" % tgt_gw

        if orch == 'openstack':
            openstack_mgmt_ip = hstr_to_ip(env.roledefs['openstack'][0])
            keystone_ip = get_keystone_ip()
            ks_auth_protocol = get_keystone_auth_protocol()
            ks_auth_port = get_keystone_auth_port()
            ks_admin_user, ks_admin_password = get_openstack_credentials()
            openstack_admin_password = get_keystone_admin_password()
            cmd += " --keystone_ip %s" % keystone_ip
            cmd += " --openstack_mgmt_ip %s" % openstack_mgmt_ip
            cmd += " --keystone_auth_protocol %s" % ks_auth_protocol
            cmd += " --keystone_auth_port %s" % ks_auth_port
            cmd += " --quantum_service_protocol %s" % get_quantum_service_protocol()
            cmd += " --keystone_admin_user %s" % ks_admin_user
            cmd += " --keystone_admin_password %s" % ks_admin_password
            if metadata_secret:
                cmd += " --metadata_secret %s" % metadata_secret

        # HA arguments
        internal_vip = get_openstack_internal_vip()
        if internal_vip:
            # Highly availbale setup
            cmd += " --internal_vip %s" % internal_vip
        external_vip = get_from_testbed_dict('ha', 'external_vip', None)
        if external_vip:
            cmd += ' --external_vip %s' % external_vip
        if manage_nova_compute == 'no':
            cmd = cmd + "  --no_contrail_openstack"
        contrail_internal_vip = get_contrail_internal_vip()
        if contrail_internal_vip:
            # Highly availbale setup with mulitple interfaces
            cmd += " --contrail_internal_vip %s" % contrail_internal_vip
        if internal_vip or contrail_internal_vip:
            cmd += " --mgmt_self_ip %s" % compute_mgmt_ip

        if configure_nova == 'no':
            cmd = cmd + "  --no_nova_config"

        # Simple Gateway(vgw) arguments
        (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list) = get_vgw_details(host_string)
        if set_vgw:
            cmd += " --vgw_public_subnet %s" % str([(';'.join(str(e) for e in public_subnet)).replace(" ","")])
            cmd += " --vgw_public_vn_name %s" % str([(';'.join(str(e) for e in public_vn_name)).replace(" ","")])
            cmd += " --vgw_intf_list %s" % str([(';'.join(str(e) for e in vgw_intf_list)).replace(" ","")])
            if gateway_routes:
                cmd += " --vgw_gateway_routes %s" % str([(';'.join(str(e) for e in gateway_routes)).replace(" ","")])

        # Contrail with vmware as orchestrator
        (vmware, esxi_data, vmware_info) = get_vmware_details(host_string)
        if vmware:
            if esxi_data:
                apply_esxi_defaults(esxi_data)
                # Esxi provisioning parameters
            	cmd += " --vmware %s" % esxi_data['ip']
                cmd += " --vmware_username %s" % esxi_data['username']
                cmd += " --vmware_passwd %s" % esxi_data['password']
                cmd += " --vmware_vmpg_vswitch %s" % esxi_data['vm_vswitch']
                cmd += " --vmware_vmpg_vswitch_mtu %s" % esxi_data['vm_vswitch_mtu']
            if vmware_info:
                # Vmware provisioning parameters
                cmd += " --vmware %s" % vmware_info['esxi']['esx_ip']
                cmd += " --vmware_username %s" % vmware_info['esxi']['esx_ip']
                cmd += " --vmware_passwd %s" % vmware_info['esxi']['esx_password']
                cmd += " --vmware_vmpg_vswitch %s" % vmware_info['esx_vm_vswitch']

        # Execute the script to provision compute node.
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-vrouter.override')
            with cd(INSTALLER_DIR):
                print cmd
                sudo(cmd)
#end setup_vrouter

@roles('cfgm')
@task
def prov_control_bgp():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))

    control_host_list=[]
    for entry in env.roledefs['control']:
        control_host_list.append(get_control_host_string(entry))
    for control_host in env.roledefs['control']:
        with settings(host_string = control_host):
            tgt_ip = hstr_to_ip(get_control_host_string(control_host))
            tgt_hostname = sudo("hostname")

        with cd(UTILS_DIR):
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

@roles('tsn')
@task
def add_tsn(restart= True):
    """Add the TSN nodes. Enable the compute nodes (mentioned with role TSN in testbed file) with TSN functionality . USAGE: fab add_tsn."""
    execute("add_tsn_node", restart, env.host_string)

@task
def add_tsn_node(restart=True,*args):
    """Enable TSN functionality in particular node. USAGE: fab add_tsn_node."""

    restart = (str(restart).lower() == 'true')
    for host_string in args:
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
        cfgm_passwd = env.passwords[env.roledefs['cfgm'][0]]
        compute_host = get_control_host_string(host_string)
        (tgt_ip, tgt_gw) = get_data_ip(host_string)
        compute_mgmt_ip= host_string.split('@')[1]
        compute_control_ip= hstr_to_ip(compute_host)
        admin_tenant_name = get_keystone_admin_tenant_name()

        # Check if nova-compute is allready running
        # Stop if running on TSN node
        with settings(host_string=host_string, warn_only=True):
            compute_hostname = sudo("hostname")
            if run("service nova-compute status | grep running").succeeded:
                # Stop the service
                run("service nova-compute stop")
                if detect_ostype() in ['ubuntu']:
                    run('echo "manual" >> /etc/init/nova-compute.override')
                else:
                    run('chkconfig nova-compute off')
                # Remove TSN node from nova manage service list
                # Mostly require when converting an exiting compute to TSN
                openstack_host = get_control_host_string(env.roledefs['openstack'][0])
                with settings(host_string=openstack_host, warn_only=True):
                    run("nova-manage service disable --host=%s --service=nova-compute" %(compute_hostname))
        orch = get_orchestrator()
        if orch is 'openstack':
            admin_user, admin_password = get_openstack_credentials()
        elif orch is 'vcenter':
            admin_user, admin_password = get_vcenter_credentials()
        keystone_ip = get_keystone_ip()
        with settings(host_string = '%s@%s' %(cfgm_user, cfgm_ip), password=cfgm_passwd):
            prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                        "--admin_user %s --admin_password %s --admin_tenant_name %s --openstack_ip %s --router_type tor-service-node" \
                        %(compute_hostname, compute_control_ip, cfgm_ip,
                          admin_user, admin_password,
                          admin_tenant_name, keystone_ip)
            run("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))
        with settings(host_string=host_string, warn_only=True):
            nova_conf_file = '/etc/contrail/contrail-vrouter-agent.conf'
            sudo("openstack-config --set %s DEFAULT agent_mode tsn" % nova_conf_file)
            if restart:
                sudo("service supervisor-vrouter restart")

@roles('toragent')
@task
def add_tor_agent(restart= True):
    """Add the tor agent nodes. Enable the compute nodes (mentioned with role toragent in testbed file) with tor agent functionality . USAGE: fab add_tor."""
    execute("add_tor_agent_node", restart, env.host_string)

@task
def add_tor_agent_node(restart=True, *args):
    """Enable tor agent functionality in particular node. USAGE: fab add_tor_agent_node."""
    restart = (str(restart).lower() == 'true')
    for host_string in args:
        with settings(host_string=host_string):
            toragent_dict = getattr(env,'tor_agent', None)
            for i in range(len(toragent_dict[host_string])):
                # Populate the argument to pass for setup-vnc-tor-agent
                tor_id= int(toragent_dict[host_string][i]['tor_id'])
                tor_name= toragent_dict[host_string][i]['tor_name']
                tor_tunnel_ip= toragent_dict[host_string][i]['tor_tunnel_ip']
                tor_vendor_name= toragent_dict[host_string][i]['tor_vendor_name']
                tsn_name=toragent_dict[host_string][i]['tor_tsn_name']
                tor_mgmt_ip=toragent_dict[host_string][i]['tor_ip']
                http_server_port = toragent_dict[host_string][i]['tor_http_server_port']
                tgt_hostname = sudo("hostname")
                agent_name= tgt_hostname + '-' + str(tor_id)
                tor_agent_host = get_control_host_string(host_string)
                tor_agent_control_ip= hstr_to_ip(tor_agent_host)
                cmd = "setup-vnc-tor-agent"
                cmd += " --self_ip %s" % tor_agent_control_ip
                cmd += " --agent_name %s" % agent_name
                cmd += " --http_server_port %s" % http_server_port
                cmd += " --discovery_server_ip %s" % hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
                cmd += " --tor_id %s" % tor_id
                cmd += " --tor_ip %s" % toragent_dict[host_string][i]['tor_ip']
                cmd += " --tor_ovs_port %s" % toragent_dict[host_string][i]['tor_ovs_port']
                cmd += " --tsn_ip %s" % toragent_dict[host_string][i]['tor_tsn_ip']
                cmd += " --tor_ovs_protocol %s" % toragent_dict[host_string][i]['tor_ovs_protocol']
                # Execute the provision toragent script
                with cd(INSTALLER_DIR):
                    sudo(cmd)
                cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
                cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
                cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
                cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
                cfgm_passwd = env.passwords[env.roledefs['cfgm'][0]]
                compute_host = get_control_host_string(host_string)
                (tgt_ip, tgt_gw) = get_data_ip(host_string)
                compute_mgmt_ip= host_string.split('@')[1]
                compute_control_ip= hstr_to_ip(compute_host)
                admin_tenant_name = get_keystone_admin_tenant_name()
                orch = get_orchestrator()
                if orch is 'openstack':
                    admin_user, admin_password = get_openstack_credentials()
                elif orch is 'vcenter':
                    admin_user, admin_password = get_vcenter_credentials()
                keystone_ip = get_keystone_ip()
                prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                            "--admin_user %s --admin_password %s --admin_tenant_name %s\
                             --openstack_ip %s --router_type tor-agent" \
                             %(agent_name, compute_control_ip, cfgm_ip,
                               admin_user, admin_password,
                               admin_tenant_name, keystone_ip)
                pr_args = "--device_name %s --vendor_name %s --device_mgmt_ip %s\
                           --device_tunnel_ip %s --device_tor_agent %s\
                           --device_tsn %s --api_server_ip %s --oper add\
                           --admin_user %s --admin_password %s\
                           --admin_tenant_name %s --openstack_ip %s"\
                    %(tor_name, tor_vendor_name, tor_mgmt_ip,tor_tunnel_ip,
                      agent_name,tsn_name,cfgm_ip, admin_user, admin_password,
                      admin_tenant_name, keystone_ip)
                with settings(host_string = '%s@%s' %(cfgm_user, cfgm_ip), password=cfgm_passwd):
                    run("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))
                    run("python /opt/contrail/utils/provision_physical_device.py %s" %(pr_args))
            if restart:
                sudo("service supervisor-vrouter restart")
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
        execute('increase_ulimits')
        execute('setup_openstack')
        if get_openstack_internal_vip():
            execute('sync_keystone_ssl_certs')
            execute('setup_cluster_monitors')
        execute('verify_openstack')
    elif orch == 'vcenter':
        execute('setup_vcenter')

@roles('build')
@task
def setup_all(reboot='True'):
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('increase_limits')
    execute('setup_database')
    execute('verify_database')
    execute('setup_orchestrator')
    execute('setup_cfgm')
    execute('verify_cfgm')
    execute('setup_control')
    execute('verify_control')
    execute('setup_collector')
    execute('verify_collector')
    execute('setup_webui')
    execute('verify_webui')
    execute('setup_vrouter')
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    if 'tsn' in env.roledefs.keys():execute('add_tsn', restart=False)
    if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():execute('add_tor_agent', restart=False)
    if reboot == 'True':
        print "Rebooting the compute nodes after setup all."
        execute('compute_reboot')
        #Clear the connections cache
        connections.clear()
        execute('verify_compute')
#end setup_all

@roles('build')
@task
def setup_without_openstack(manage_nova_compute='yes', reboot='True'):
    """Provisions required contrail packages in all nodes as per the role definition except the openstack.
       User has to provision the openstack node with their custom openstack pakckages.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute will be skipped in the compute node.
    """
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('increase_limits')
    execute('setup_database')
    execute('verify_database')
    execute('setup_cfgm')
    execute('verify_cfgm')
    execute('setup_control')
    execute('verify_control')
    execute('setup_collector')
    execute('verify_collector')
    execute('setup_webui')
    execute('verify_webui')
    execute('setup_vrouter', manage_nova_compute)
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    if 'tsn' in env.roledefs.keys():execute('add_tsn', restart=False)
    if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():execute('add_tor_agent', restart=False)
    if reboot == 'True':
        print "Rebooting the compute nodes after setup all."
        execute(compute_reboot)
        # Clear the connections cache
        connections.clear()
        execute('verify_compute')

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
        execute(increase_limits)
        execute(increase_ulimits)
        execute(setup_database)
        execute(verify_database)
        execute(setup_orchestrator)
        execute(setup_cfgm)
        execute(verify_cfgm)
        execute(setup_control)
        execute(verify_control)
        execute(setup_collector)
        execute(verify_collector)
        execute(setup_webui)
        execute(verify_webui)
        execute(stop_database)
        execute(delete_cassandra_db_files)
        execute(start_database)
        execute(stop_cfgm)
        execute(config_server_reset, 'add', [env.roledefs['cfgm'][0]])
        execute(run_cmd, env.roledefs['cfgm'][0], "service supervisor-config restart")
        execute(start_cfgm)
        execute(restart_collector)
        if 'tsn' in env.roledefs.keys():execute(add_tsn)
        if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():execute(add_tor_agent)
        sleep(120)
    except SystemExit:
        execute(config_server_reset, 'delete', [env.roledefs['cfgm'][0]])
        raise SystemExit("\nReset config Failed.... Aborting")
    else:
        execute(config_server_reset, 'delete', [env.roledefs['cfgm'][0]])
    sleep(60)
    execute(prov_control_bgp)
    execute(prov_external_bgp)
    execute(prov_metadata_services)
    execute(prov_encap_type)
    execute(setup_remote_syslog)
    execute(setup_vrouter)
    execute(compute_reboot)
#end reset_config

@roles('build')
@task
def prov_esxi(deb=None):
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Error: esxi_hosts block is not defined in testbed file.Exiting'
        return
    orch = get_orchestrator()
    if orch is 'vcenter':
        vcenter_info = getattr(env, 'vcenter', None)
        if not vcenter_info:
            print 'Error: vcenter block is not defined in testbed file.Exiting'
            return
        for esxi_node in esxi_info.keys():
            esxi_data = esxi_info[esxi_node]
            compute_vm_info = esxi_data['contrail_vm']
            apply_esxi_defaults(esxi_data)
            provision_esxi_node(deb, vcenter_info, esxi_data, compute_vm_info)
    else:
        for host in esxi_info.keys():
            apply_esxi_defaults(esxi_info[host])
            configure_esxi_network(esxi_info[host])
            create_esxi_compute_vm(esxi_info[host])
#end prov_compute_vm

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
    provision_vcenter(vcenter_info, esxi_info)

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
    run("(source /etc/contrail/openstackrc; nova aggregate-create esx esx)")
    cmd = "(source /etc/contrail/openstackrc; nova aggregate-add-host esx %s)"
    for server in esx:
        run(cmd % esx[server]['contrail_vm']['name'])
# end setup_esx_zone

@hosts(env.roledefs['openstack'][0:1])
@task
def setup_zones():
    """Setup availability zones."""
    setup_esx_zone()
#end setup_zones


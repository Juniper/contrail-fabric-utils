import os
import string
import textwrap
import json
import socket
from time import sleep
from multiprocessing import cpu_count

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
from fabfile.utils.commandline import *
from fabfile.tasks.tester import setup_test_env
from fabfile.tasks.rabbitmq import setup_rabbitmq_cluster
from fabfile.tasks.vmware import provision_vcenter, provision_dvs_fab,\
        configure_esxi_network, create_esxi_compute_vm, deprovision_vcenter,\
        provision_vcenter_features, provision_pci_fab
from fabfile.utils.cluster import get_vgw_details, get_orchestrator,\
        get_vmware_details, get_tsn_nodes, get_toragent_nodes,\
        get_esxi_vms_and_hosts, get_mode, is_contrail_node
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

@roles('cfgm')
@task
def fix_cfgm_config():
    """Regenerate the config file in all the cfgm nodes"""
    if env.roledefs['cfgm']:
        execute("fix_cfgm_config_node", env.host_string)

@task
def fix_cfgm_config_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
            cmd = frame_vnc_config_cmd(host_string, "update-cfgm-config")
            sudo(cmd)

@roles('collector')
@task
def fix_collector_config():
    """Regenerate the collector file in all the analytics nodes"""
    if env.roledefs['collector']:
        execute("fix_collector_config_node", env.host_string)

@task
def fix_collector_config_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
            cmd = frame_vnc_collector_cmd(host_string, "update-collector-config")
            sudo(cmd)

@roles('webui')
@task
def fix_webui_config():
    """Regenerate the webui config file in all the webui nodes"""
    if env.roledefs['webui']:
        execute("fix_webui_config_node", env.host_string)

@task
def fix_webui_config_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
            cmd = frame_vnc_webui_cmd(host_string, "update-webui-config")
            sudo(cmd)

def fixup_restart_haproxy_in_all_cfgm(nworkers):
    template = string.Template("""
#contrail-config-marker-start

global
        tune.maxrewrite 1024

listen contrail-config-stats :5937
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend quantum-server *:9696
    default_backend    quantum-server-backend

frontend  contrail-api *:8082
    default_backend    contrail-api-backend
    timeout client 3m

frontend  contrail-discovery *:5998
    default_backend    contrail-discovery-backend

backend quantum-server-backend
    option nolinger
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9697 check

backend contrail-api-backend
    option nolinger
    timeout server 3m
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

$__tor_agent_ha_config__

$__rabbitmq_config__
#contrail-config-marker-end
""")

    q_listen_port = 9697
    q_server_lines = ''
    api_listen_port = 9100
    api_server_lines = ''
    disc_listen_port = 9110
    disc_server_lines = ''
    tor_agent_ha_config = ''
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

    # create TOR agent configuration for the HA proxy
    if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():
        tor_agent_ha_config = get_all_tor_agent_haproxy_config()

    for host_string in env.roledefs['cfgm']:
        haproxy_config = template.safe_substitute({
            '__contrail_quantum_servers__': q_server_lines,
            '__contrail_api_backend_servers__': api_server_lines,
            '__contrail_disc_backend_servers__': disc_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            '__rabbitmq_config__': rabbitmq_config,
            '__tor_agent_ha_config__': tor_agent_ha_config,
            })

        with settings(host_string=host_string):
            # chop old settings including pesky default from pkg...
            tmp_fname = "/tmp/haproxy-%s-config" %(host_string)
            get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-config-marker-start/,/^#contrail-config-marker-end/d' %s" %(tmp_fname))
                local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(tmp_fname))
                local('grep -q "tune.bufsize 16384" %s || sed -i "/^global/a\\        tune.bufsize 16384" %s' % (tmp_fname, tmp_fname))
                local('grep -q "tune.maxrewrite 1024" %s || sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % (tmp_fname, tmp_fname))
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

# Get HA proxy configuration for a TOR agent
def get_tor_agent_haproxy_config(proxy_name, key, ha_dict):
    tor_agent_ha_config = '\n'
    port_list = ha_dict[key]
    ha_dict_len = len(port_list)
    if ha_dict_len == 0:
        return tor_agent_ha_config
    ip2 = None
    if "-" in key:
        ip1 = key.split('-')[0]
        ip2 = key.split('-')[1]
    else:
        ip1 = key
    tor_agent_ha_config = tor_agent_ha_config + 'listen %s\n' %(proxy_name)
    tor_agent_ha_config = tor_agent_ha_config + '    option tcpka\n'
    tor_agent_ha_config = tor_agent_ha_config + '    mode tcp\n'
    tor_agent_ha_config = tor_agent_ha_config + '    bind :%s' %(port_list[0])
    for i in range(1, ha_dict_len):
        tor_agent_ha_config = tor_agent_ha_config + ',:%s' %(port_list[i])
    tor_agent_ha_config = tor_agent_ha_config + '\n'
    tor_agent_ha_config = tor_agent_ha_config + '    server %s %s check inter 2000\n' %(ip1, ip1)
    if ip2 != None:
        tor_agent_ha_config = tor_agent_ha_config + '    server %s %s check inter 2000\n' %(ip2, ip2)
        tor_agent_ha_config = tor_agent_ha_config + '    balance leastconn\n'
    tor_agent_ha_config = tor_agent_ha_config + '\n'
    return tor_agent_ha_config
#end get_tor_agent_haproxy_config

def get_tor_agent_id(entry):
    tor_id = -1
    if 'tor_id' in entry:
        tor_id= int(entry['tor_id'])
    elif 'tor_agent_id' in entry:
        tor_id= int(entry['tor_agent_id'])
    else:
        print 'tor-agent-id configuration is missing in testbed file'
    return tor_id
#end get_tor_agent_id

# Given a host_string and tor_name, return the standby tor-agent info identified
# by index and host-string of tor-agent
def get_standby_info(skip_host, match_tor_name):
    toragent_dict = getattr(env,'tor_agent', None)
    tor_agent_host_list = get_toragent_nodes()
    for host in tor_agent_host_list:
        if host == skip_host:
            continue
        for i in range(len(toragent_dict[host])):
            tor_name= toragent_dict[host][i]['tor_name']
            if tor_name == match_tor_name:
                return (i, host)
    return (-1, None)
#end get_standby_info

def make_key(tsn1, tsn2):
    if tsn1 < tsn2:
        return tsn1 + "-" + tsn2
    return tsn2 + "-" + tsn1

# Get HA proxy configuration for all TOR agents
def get_all_tor_agent_haproxy_config():
    toragent_dict = getattr(env,'tor_agent', None)
    master_standby_dict = {}
    tor_agent_host_list = get_toragent_nodes()
    for host in tor_agent_host_list:
        for i in range(len(toragent_dict[host])):
            tor_name= toragent_dict[host][i]['tor_name']
            tsn1 = toragent_dict[host][i]['tor_tsn_ip']
            port1 = toragent_dict[host][i]['tor_ovs_port']
            standby_tor_idx, standby_host = get_standby_info(host, tor_name)
            key = tsn1
            if (standby_tor_idx != -1 and standby_host != None):
                tsn2 = toragent_dict[standby_host][standby_tor_idx]['tor_tsn_ip']
                port2 = toragent_dict[standby_host][standby_tor_idx]['tor_ovs_port']
                if port1 == port2:
                    key = make_key(tsn1, tsn2)
                else:
                    print "Tor Agents (%s, %d) and (%s, %d) are configured as \
                        redundant agents but don't have same ovs_port" \
                        %(host, i, standby_host, standby_tor_idx)
            if not key in master_standby_dict:
                master_standby_dict[key] = []
            if not port1 in master_standby_dict[key]:
                master_standby_dict[key].append(port1)
    i = 1
    cfg_str = ""
    for key in master_standby_dict.keys():
        proxy_name = "contrail-tor-agent-" + str(i)
        i = i +  1
        cfg_str = cfg_str + get_tor_agent_haproxy_config(proxy_name, key, master_standby_dict)
    return cfg_str
#end test_task

@roles('cfgm')
@task
def setup_haproxy_config():
    """Provisions HA proxy service in all nodes defined in cfgm role."""
    if env.roledefs['cfgm']:
        execute("setup_haproxy_config_node", env.host_string)

@task
def setup_haproxy_config_node(*args):
    """Provisions HA proxy service in one or list of nodes."""

    nworkers = 1
    fixup_restart_haproxy_in_all_cfgm(nworkers)
#end setup_haproxy_node

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
            local('grep -q "tune.bufsize 16384" %s || sed -i "/^global/a\\        tune.bufsize 16384" %s' % (tmp_fname, tmp_fname))
            local('grep -q "tune.maxrewrite 1024" %s || sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % (tmp_fname, tmp_fname))
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
                local('grep -q "tune.bufsize 16384" %s || sed -i "/^global/a\\        tune.bufsize 16384" %s' % (tmp_fname, tmp_fname))
                local('grep -q "tune.maxrewrite 1024" %s || sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % (tmp_fname, tmp_fname))

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

    for host_string in args:
        # Enable settings for Ubuntu
        with  settings(host_string=host_string):
            enable_haproxy()
    nworkers = 1
    fixup_restart_haproxy_in_all_cfgm(nworkers)

    for host_string in args:
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-config.override')
                    sudo('rm /etc/init/neutron-server.override')

            # Frame the command line to provision config node
            cmd = frame_vnc_config_cmd(host_string)
            # Execute the provision config script
            with cd(INSTALLER_DIR):
                sudo(cmd)

            orch = get_orchestrator()
            if orch == 'vcenter' or 'vcenter_compute' in env.roledefs:
                #create the static esxi:vrouter map file
                esxi_info = getattr(testbed, 'esxi_hosts', None)
                tmp_fname = "/tmp/ESXiToVRouterIp-%s" %(host_string)
                for esxi_host in esxi_info:
                    esxi_ip = esxi_info[esxi_host]['ip']
                    vrouter_ip_string = esxi_info[esxi_host]['contrail_vm']['host']
                    vrouter_ip = hstr_to_ip(vrouter_ip_string)
                    local("echo '%s:%s' >> %s" %(esxi_ip, vrouter_ip, tmp_fname))
                put(tmp_fname, "/etc/contrail/ESXiToVRouterIp.map", use_sudo=True)
                local("rm %s" %(tmp_fname))

                # Frame the command  to provision vcenter-plugin
                vcenter_info = getattr(env, 'vcenter', None)
                if not vcenter_info:
                    print 'Error: vcenter block is not defined in testbed file.Exiting'
                    return
                cassandra_ip_list = [hstr_to_ip(get_control_host_string(\
                    cassandra_host)) for cassandra_host in env.roledefs['database']]
                cfgm_ip = get_contrail_internal_vip() or\
                    hstr_to_ip(host_string);
                cmd = "setup-vcenter-plugin"
                cmd += " --vcenter_url %s" % vcenter_info['server']
                cmd += " --vcenter_username %s" % vcenter_info['username']
                cmd += " --vcenter_password %s" % vcenter_info['password']
                cmd += " --vcenter_datacenter %s" % vcenter_info['datacenter']
                cmd += " --vcenter_dvswitch %s" % vcenter_info['dv_switch']['dv_switch_name']
                if 'ipfabricpg' in vcenter_info.keys():
                    cmd += " --vcenter_ipfabricpg %s" % vcenter_info['ipfabricpg']
                else:
                    # If unspecified, set it to default value
                    cmd += " --vcenter_ipfabricpg contrail-fab-pg"
                cmd += " --api_hostname %s" % cfgm_ip
                cmd += " --api_port 8082"
                zk_servers_ports = ','.join(['%s:2181' %(s) for s in cassandra_ip_list])
                cmd += " --zookeeper_serverlist %s" % zk_servers_ports
                if 'vcenter_compute' in env.roledefs:
                    cmd += " --vcenter_mode vcenter-as-compute"
                    # Pass keystone arguments in case of vcenter-as-compute mode
                    authserver_ip = get_authserver_ip()
                    ks_admin_user, ks_admin_password = get_authserver_credentials()
                    cmd += " --keystone_ip %s" % authserver_ip
                    cmd += " --keystone_admin_user %s" % ks_admin_user
                    cmd += " --keystone_admin_passwd %s" % ks_admin_password
                    cmd += " --keystone_admin_tenant_name %s" % get_admin_tenant_name()
                    cmd += " --keystone_auth_protocol %s" % get_authserver_protocol()
                    cmd += " --keystone_auth_port %s" % get_authserver_port()
                else:
                    cmd += " --vcenter_mode vcenter-only"

                # Execute the provision vcenter-plugin script
                with cd(INSTALLER_DIR):
                    sudo(cmd)

    # HAPROXY fixups
    haproxy = get_haproxy_opt()
    if haproxy:
        fixup_restart_haproxy_in_all_compute()
        fixup_restart_haproxy_in_all_openstack()
#end setup_cfgm_node


def fixup_ceilometer_conf_common():
    conf_file = '/etc/ceilometer/ceilometer.conf'
    amqp_server_ip = get_openstack_amqp_server()
    sudo("openstack-config --set %s DEFAULT rabbit_host %s" % (conf_file, amqp_server_ip))
    value = "/var/log/ceilometer"
    sudo("openstack-config --set %s DEFAULT log_dir %s" % (conf_file, value))
    value = "a74ca26452848001921c"
    openstack_sku = get_openstack_sku()
    if openstack_sku == 'havana':
        sudo("openstack-config --set %s DEFAULT metering_secret %s" % (conf_file, value))
    else:
        sudo("openstack-config --set %s publisher metering_secret %s" % (conf_file, value))
    sudo("openstack-config --set %s DEFAULT auth_strategy keystone" % conf_file)
#end fixup_ceilometer_conf_common

def fixup_ceilometer_conf_keystone(openstack_ip):
    conf_file = '/etc/ceilometer/ceilometer.conf'
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
#end fixup_ceilometer_conf_keystone

def fixup_ceilometer_pipeline_conf(analytics_ip):
    import yaml
    rconf_file = '/etc/ceilometer/pipeline.yaml'
    conf_file = 'pipeline.yaml'
    ltemp_dir = tempfile.mkdtemp()
    get(rconf_file, ltemp_dir)
    with open('%s/%s' % (ltemp_dir, conf_file)) as fap:
        data = fap.read()
    pipeline_dict = yaml.safe_load(data)
    # If already configured with 'contrail_source' and/or 'contrail_sink' exit
    for source in pipeline_dict['sources']:
        if source['name'] == 'contrail_source':
            return
    for sink in pipeline_dict['sinks']:
        if sink['name'] == 'contrail_sink':
            return
    # Edit meters in sources to exclude floating IP meters if '*' is
    # configured
    for source in pipeline_dict['sources']:
        for mname in source['meters']:
            if mname == '*':
                source['meters'].append('!ip.floating.*')
                print('Excluding floating IP meters from source %s' % (source['name']))
                break
    # Add contrail source and sinks to the pipeline
    interval = int(get_ceilometer_interval())
    contrail_source = {'interval': interval,
                       'meters': ['ip.floating.receive.bytes',
                                  'ip.floating.receive.packets',
                                  'ip.floating.transmit.bytes',
                                  'ip.floating.transmit.packets'],
                       'name': 'contrail_source',
                       'sinks': ['contrail_sink']}
    contrail_source['resources'] = ['contrail://%s:8081/' % (analytics_ip)]
    contrail_sink = {'publishers': ['rpc://'],
                     'transformers': None,
                     'name': 'contrail_sink'}
    pipeline_dict['sources'].append(contrail_source)
    pipeline_dict['sinks'].append(contrail_sink)
    with open('%s/%s' % (ltemp_dir, conf_file), 'w') as fap:
        yaml.safe_dump(pipeline_dict, fap, explicit_start=True,
                   default_flow_style=False, indent=4)
    rtemp_dir = sudo('(tempdir=$(mktemp -d); echo $tempdir)')
    put('%s/%s' % (ltemp_dir, conf_file), rtemp_dir, use_sudo=True)
    sudo('mv %s/%s %s' % (rtemp_dir, conf_file, rconf_file))
    local('rm -rf %s' % (ltemp_dir))
    sudo('rm -rf %s' % (rtemp_dir))
#end fixup_ceilometer_pipeline_conf

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
@roles('compute')
def setup_ceilometer_compute():
    """Provisions ceilometer compute services in all nodes defined in compute role."""
    if env.roledefs['compute']:
        execute("setup_ceilometer_compute_node", env.host_string)

@task
def setup_ceilometer_compute_node(*args):
    """Provisions ceilometer compute services in one or list of nodes. USAGE: fab setup_ceilometer_compute_node:user@1.1.1.1,user@2.2.2.2"""
    openstack_host = env.roledefs['openstack'][0]
    for host_string in args:
        with settings(host_string=host_string):
            os_type = detect_ostype()
            with settings(warn_only=True):
                compute_ceilometer_present = sudo("grep '^instance_usage_audit =' /etc/nova/nova.conf").succeeded
            if not compute_ceilometer_present:
                config_cmd = "openstack-config --set /etc/nova/nova.conf DEFAULT"
                sudo("%s notification_driver ceilometer.compute.nova_notifier" % config_cmd)
                sudo("%s notification_driver nova.openstack.common.notifier.rpc_notifier" % config_cmd)
                sudo("%s notify_on_state_change vm_and_task_state" % config_cmd)
                sudo("%s instance_usage_audit_period hour" % config_cmd)
                sudo("%s instance_usage_audit True" % config_cmd)
                if os_type == 'ubuntu':
                    nova_services = ['nova-compute']
                elif os_type in ['redhat']:
                    nova_services = ['openstack-nova-compute']
                else:
                    raise RuntimeError("Unsupported OS Type (%s)", os_type)
                for svc in nova_services:
                    sudo("service %s restart" % (svc))

            if host_string != openstack_host:
                # copy over ceilometer.conf from the first openstack node
                conf_file = '/etc/ceilometer/ceilometer.conf'
                local_tempdir = tempfile.mkdtemp()
                with lcd(local_tempdir):
                    with settings(host_string = openstack_host):
                        get(conf_file, local_tempdir)
                tempdir = sudo('(tempdir=$(mktemp -d); echo $tempdir)')
                put('%s/ceilometer.conf' % (local_tempdir), tempdir, use_sudo=True)
                sudo('mv %s/ceilometer.conf %s' % (tempdir, conf_file))
                local('rm -rf %s' % (local_tempdir))
                sudo('rm -rf %s' % (tempdir))
                if os_type == 'ubuntu':
                    ceilometer_services = ['ceilometer-agent-compute']
                elif os_type in ['redhat']:
                    ceilometer_services = ['openstack-ceilometer-compute']
                else:
                    raise RuntimeError("Unsupported OS Type (%s)", os_type)
                for svc in ceilometer_services:
                    sudo("service %s restart" % (svc))

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
def setup_ceilometer():
    """Provisions ceilometer services in all nodes defined in openstack role."""
    if env.roledefs['openstack'] and env.host_string == env.roledefs['openstack'][0]:
        execute("setup_ceilometer_node", env.host_string)

    execute("setup_image_service_node", env.host_string)
    execute("setup_network_service_node", env.host_string)
    execute("setup_identity_service_node", env.host_string)

@task
def setup_ceilometer_node(*args):
    """Provisions ceilometer services in one or list of nodes. USAGE: fab setup_ceilometer_node:user@1.1.1.1,user@2.2.2.2"""
    analytics_ip = hstr_to_ip(env.roledefs['collector'][0])
    for host_string in args:
        self_host = get_control_host_string(host_string)
        self_ip = hstr_to_ip(self_host)

        with settings(host_string=host_string):
            openstack_sku = get_openstack_sku()

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
            conf_file = "/etc/ceilometer/ceilometer.conf"
            database_host_list = [get_control_host_string(entry)\
                                     for entry in env.roledefs['database']]
            database_ip_list = ["%s:27017" % (hstr_to_ip(db_host))\
                                   for db_host in database_host_list]
            database_ip_str = ','.join(database_ip_list)
            value = "mongodb://ceilometer:CEILOMETER_DBPASS@" + database_ip_str + \
                        "/ceilometer?replicaSet=rs-ceilometer"
            if openstack_sku == 'havana':
                sudo("openstack-config --set %s DEFAULT connection %s" % (conf_file, value))
            else:
                sudo("openstack-config --set %s database connection %s" % (conf_file, value))
            fixup_ceilometer_conf_common()
            #keystone auth params
            cmd = "source /etc/contrail/openstackrc;keystone user-get ceilometer"
            with settings(warn_only=True):
                output = sudo(cmd)
            count = 1
            while not output.succeeded and (
                    "Unable to establish connection" in output or
                    "Service Unavailable (HTTP 503)" in output):
                count += 1
                if count > 10:
                    raise RuntimeError("Unable to connect to keystone")
                sleep(1)
                with settings(warn_only=True):
                    output = sudo(cmd)
            if not output.succeeded:
                sudo("source /etc/contrail/openstackrc;keystone user-create --name=ceilometer --pass=CEILOMETER_PASS --tenant=service --email=ceilometer@example.com")
                sudo("source /etc/contrail/openstackrc;keystone user-role-add --user=ceilometer --tenant=service --role=admin")

            fixup_ceilometer_conf_keystone(self_ip)

            #create keystone service and endpoint
            with settings(warn_only=True):
                ceilometer_service_exists = sudo("source /etc/contrail/openstackrc;keystone service-list | grep ceilometer").succeeded
            if not ceilometer_service_exists:
                sudo("source /etc/contrail/openstackrc;keystone service-create --name=ceilometer --type=metering --description=\"Telemetry\"")
                sudo("source /etc/contrail/openstackrc;keystone endpoint-create --service-id=$(keystone service-list | awk '/ metering / {print $2}') --publicurl=http://%s:8777 --internalurl=http://%s:8777 --adminurl=http://%s:8777 --region=RegionOne" %(self_ip, self_ip, self_ip))
            # Fixup ceilometer pipeline cfg
            fixup_ceilometer_pipeline_conf(analytics_ip)
            for svc in ceilometer_services:
                sudo("service %s restart" %(svc))
#end setup_ceilometer_node

@task
def setup_network_service_node(*args):
    """Provisions network services in one or list of nodes.
       USAGE: fab setup_network_service_node:user@1.1.1.1,user@2.2.2.2"""
    conf_file = '/etc/neutron/neutron.conf'
    neutron_config = {'DEFAULT' : {'notification_driver' : 'neutron.openstack.common.notifier.rpc_notifier'}
                     }
    for host_string in args:
        for section, key_values in neutron_config.iteritems():
            for key, value in key_values.iteritems():
                sudo("openstack-config --set %s %s %s %s" % (conf_file, section, key, value))
        sudo("service neutron-server restart")
#end setup_network_service_node

@task
def setup_identity_service_node(*args):
    """Provisions identity services in one or list of nodes.
       USAGE: fab setup_identity_service_node:user@1.1.1.1,user@2.2.2.2"""
    amqp_server_ip = get_openstack_amqp_server()
    rabbit_port    = "5672"
    
    # If HA is enabled, then use the frontend HAProxy Rabbit port
    if get_openstack_internal_vip():
        rabbit_port = "5673"

    conf_file = '/etc/keystone/keystone.conf'
    keystone_configs = {'DEFAULT' : {'notification_driver' : 'messaging',
                                     'rabbit_host' : '%s' % amqp_server_ip,
                                     'rabbit_port' : '%s' % rabbit_port }
                      }
    for host_string in args:
        for section, key_values in keystone_configs.iteritems():
            for key, value in key_values.iteritems():
                sudo("openstack-config --set %s %s %s %s" % (conf_file, section, key, value))
        sudo("service keystone restart")
#end setup_identity_service_node

@task
def setup_image_service_node(*args):
    """Provisions image services in one or list of nodes. USAGE: fab setup_image_service_node:user@1.1.1.1,user@2.2.2.2"""
    amqp_server_ip = get_openstack_amqp_server()
    for host_string in args:
        openstack_sku = get_openstack_sku()

        glance_configs = {'DEFAULT' : {'notification_driver' : 'messaging',
                                       'rpc_backend' : 'rabbit',
                                       'rabbit_host' : '%s' % amqp_server_ip,
                                       'rabbit_password' : 'guest'}
                        }
        if openstack_sku == 'havana':
            glance_configs['DEFAULT']['notifier_strategy'] = 'rabbit'
            glance_configs['DEFAULT']['rabbit_userid'] = 'guest'

        conf_file = "/etc/glance/glance-api.conf"
        for section, key_values in glance_configs.iteritems():
            for key, value in key_values.iteritems():
                sudo("openstack-config --set %s %s %s %s" % (conf_file, section, key, value))
        sudo("service glance-registry restart")
        sudo("service glance-api restart")
#end setup_image_service_node

@task
@roles('openstack')
def setup_openstack():
    """Provisions openstack services in all nodes defined in openstack role."""
    if env.roledefs['openstack']:
        execute("setup_openstack_node", env.host_string)
        # Blindly run setup_openstack twice for Ubuntu
        #TODO Need to remove this finally
        if detect_ostype() == 'ubuntu':
            execute("setup_openstack_node", env.host_string)
        if is_package_installed('contrail-openstack-dashboard'):
            execute('setup_contrail_horizon_node', env.host_string)
        if is_ceilometer_provision_supported():
            setup_ceilometer()

@task
@roles('openstack')
def setup_nova_aggregate():
    if get_orchestrator() == 'vcenter' or 'vcenter_compute' in env.roledefs:
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
        if hypervisor == 'docker':
            with settings(host_string=compute_host,
                          password=get_env_passwords(compute_host)):
                host_name = sudo("hostname")
            env_vars = 'source /etc/contrail/openstackrc'
            retry = 10
            while retry:
                with settings(warn_only=True, prefix='source /etc/contrail/openstackrc'):
                    with prefix('source /etc/contrail/openstackrc'):
                        #aggregate_list = sudo("(%s; nova aggregate-list)" % env_vars)
                        aggregate_list = sudo("(nova aggregate-list)")
                        if aggregate_list.failed: # Services might be starting up after reboot
                            sleep(6)
                            retry -= 1
                            continue
                        aggregate_details = sudo("(nova aggregate-details %s)" % (hypervisor))
                        if host_name not in aggregate_details:
                            if hypervisor not in aggregate_list:
                                create = sudo("(nova aggregate-create %s nova/%s)" % (hypervisor, hypervisor))
                                if create.failed: # Services might be starting up after reboot
                                    continue
                            if sudo("(nova aggregate-add-host %s %s)" % (hypervisor, host_name)).failed:
                                continue # Services might be starting up after reboot
                        break # Stop retrying as the aggregate is created and compute is added.

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
    execute('add_openstack_reserverd_ports')
    for host_string in args:
        # Frame the command line to provision openstack
        cmd = frame_vnc_openstack_cmd(host_string)
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
def setup_redis_server_node(*args):
    """Provisions redis server in one or list of nodes.
       USAGE: fab setup_redis_server_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # We need the redis to be listening on *, comment bind line
        with settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                redis_svc_name = 'redis-server'
                redis_conf_file = '/etc/redis/redis.conf'
                do_chkconfig = False
                check_svc_started = True
            else:
                redis_svc_name = 'redis'
                redis_conf_file = '/etc/redis.conf'
                do_chkconfig = True
                check_svc_started = False

            with settings(warn_only=True):
                sudo("service %s stop" % (redis_svc_name))
            sudo("sed -i -e '/^[ ]*bind/s/^/#/' %s" % (redis_conf_file))
            # Set the lua-time-limit to 15000 milliseconds
            sudo("sed -i -e 's/lua-time-limit.*/lua-time-limit 15000/' %s" % (redis_conf_file))
            # If redis passwd specified, add that to the conf file
            if get_redis_password():
                sudo("sed -i '/^# requirepass/ c\ requirepass %s' %s" % (get_redis_password(), redis_conf_file))
            # Disable persistence
            dbfilename = sudo("grep '^dbfilename' %s | awk '{print $2}'" % (redis_conf_file))
            if dbfilename:
                dbdir = sudo("grep '^dir' %s | awk '{print $2}'" % (redis_conf_file))
                if dbdir:
                    sudo("rm -f %s/%s" % (dbdir, dbfilename))
            sudo("sed -i -e '/^[ ]*save/s/^/#/' %s" % (redis_conf_file))
            sudo("sed -i -e '/^[ ]*dbfilename/s/^/#/' %s" % (redis_conf_file))
            if do_chkconfig:
                sudo("chkconfig %s on" % (redis_svc_name))
            sudo("service %s start" % (redis_svc_name))
            if check_svc_started:
                # Check if the redis-server is running, if not, issue start again
                count = 1
                with settings(warn_only=True):
                    while sudo("service %s status | grep not" % (redis_svc_name)).succeeded:
                        count += 1
                        if count > 10:
                            raise RuntimeError("redis-server did not start successfully")
                        sleep(1)
                        sudo("service %s restart" % (redis_svc_name))
#end setup_redis_server_node


@task
@EXECUTE_TASK
@roles('vcenter_compute')
def setup_vcenter_compute():
    execute("setup_vcenter_compute_node", env.host_string)

@task
def setup_vcenter_compute_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
             if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                     setup_vrouter('yes', 'yes')

@task
def setup_collector_node(*args):
    """Provisions collector services in one or list of nodes. USAGE: fab setup_collector_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        # Setup redis server
        execute("setup_redis_server_node", host_string)
        # Frame the command line to provision collector
        cmd = frame_vnc_collector_cmd(host_string)
        # Execute the provision collector script
        with settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-analytics.override')
            with cd(INSTALLER_DIR):
                print cmd
                sudo(cmd)
#end setup_collector_node

@task
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
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-database.override')
            with cd(INSTALLER_DIR):
                sudo(cmd)
#end setup_database

@task
@roles('database')
def fix_zookeeper_config():
    """Update the zookeeper config based on the new configuration"""
    if env.roledefs['database']:
        execute("fix_zookeeper_config_node", env.host_string)

@task
def fix_zookeeper_config_node(*args):
    for host_string in args:
        cmd = frame_vnc_database_cmd(host_string, 'update-zoo-servers')
        sudo(cmd)

@task
@roles('database')
def restart_all_zookeeper_servers():
    """Restarts all zookeeper server in all the database nodes"""
    if env.roledefs['database']:
        execute("restart_all_zookeeper_servers_node", env.host_string)

@task
def restart_all_zookeeper_servers_node(*args):
    for host_string in args:
        cmd = frame_vnc_database_cmd(host_string, 'restart-zoo-server')
        sudo(cmd)


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
        # Setup redis server node
        execute("setup_redis_server_node", host_string)
        # Frame the command line to provision webui
        cmd = frame_vnc_webui_cmd(host_string)
        # Execute the provision webui script
        with settings(host_string=host_string):
            with settings(warn_only=True):
                if detect_ostype() == 'ubuntu':
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
        cmd = frame_vnc_control_cmd(host_string)
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-control.override')
                    sudo('rm /etc/init/supervisor-dns.override')
            with cd(INSTALLER_DIR):
                sudo(cmd)
                if detect_ostype() in ['centos', 'redhat', 'fedora', 'centoslinux']:
                    sudo("service supervisor-control restart")
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
    if env.roledefs['compute'] or 'vcenter_compute' in env.roledefs:
       # Launching of VM is not surrently supported in TSN node.
       # Not proviosning nova_compute incase the compute node is TSN.
       if env.host_string in get_tsn_nodes():
           manage_nova_compute='no'
           configure_nova='no'
       if get_mode(env.host_string) == 'vcenter':
           manage_nova_compute='no'
           configure_nova='no'
       execute("setup_only_vrouter_node", manage_nova_compute, configure_nova,  env.host_string)
       if is_ceilometer_compute_provision_supported():
           execute("setup_ceilometer_compute_node", env.host_string)

@task
def setup_vrouter_node(*args):
    """Provisions nova-compute and vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute("setup_only_vrouter_node", 'yes', 'yes', *args)
    if is_ceilometer_compute_provision_supported():
        execute("setup_ceilometer_compute_node", *args)

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

    for host_string in args:
        # Enable haproxy for Ubuntu
        with  settings(host_string=host_string):
            enable_haproxy()
        haproxy = get_haproxy_opt()
        if haproxy:
            # setup haproxy and enable
            fixup_restart_haproxy_in_one_compute(host_string)

        # Frame the command line to provision compute node.
        cmd = frame_vnc_compute_cmd(host_string,
                                    manage_nova_compute=manage_nova_compute,
                                    configure_nova=configure_nova)

        # Setup hugepages if necessary
        setup_hugepages_node(host_string)

        # Setup affinity mask if necessary
        setup_coremask_node(host_string)
        # Setup vr_mpls_labels, vr_nexthops, vr_vrfs, vr_bridge_entries
        # if necessary
        dpdk_increase_vrouter_limit()

        # Execute the script to provision compute node.
        with  settings(host_string=host_string):
            if detect_ostype() == 'ubuntu':
                with settings(warn_only=True):
                    sudo('rm /etc/init/supervisor-vrouter.override')
            with cd(INSTALLER_DIR):
                print cmd
                sudo(cmd)
#end setup_vrouter

@task
@EXECUTE_TASK
def prov_config():
    execute("prov_config_node", env.host_string)

@task
def prov_config_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
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
def prov_database():
    execute("prov_database_node", env.host_string)

@task
def prov_database_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
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
def prov_analytics():
    execute("prov_analytics_node", env.host_string)

@task
def prov_analytics_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
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
    execute("prov_control_bgp_node", env.host_string)

@task
def prov_control_bgp_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
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
                md5_value = get_bgp_md5(env.host_string)
                #if condition required because without it, it will configure literal 'None' md5 key
                if md5_value:
                    cmd += " --md5 %s" % md5_value
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
    execute("prov_external_bgp_node", env.host_string)

@task
def prov_external_bgp_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
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
    execute("prov_metadata_services_node", env.host_string)

@task
def prov_metadata_services_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
            cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
            orch = get_orchestrator()
            if orch is 'none':
                return

            if orch is 'openstack':
                openstack_host = get_control_host_string(env.roledefs['openstack'][0])
                ipfabric_service_ip = get_openstack_internal_vip() or hstr_to_ip(openstack_host)
                ipfabric_service_port = '8775'
            elif orch is 'vcenter':
                ipfabric_service_ip = get_authserver_ip()
                ipfabric_service_port = get_authserver_port()
            admin_user, admin_password = get_authserver_credentials()
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
    execute("prov_encap_type_node", env.host_string)

@task
def prov_encap_type_node(*args):
    for host_string in args:
        with settings(host_string = host_string):
            cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
            admin_user, admin_password = get_authserver_credentials()
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
    if is_contrail_node(env.host_string):
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

@hosts(get_tsn_nodes())
@task
def add_tsn(restart= True):
    """Add the TSN nodes. Enable the compute nodes (mentioned with role TSN in testbed file) with TSN functionality . USAGE: fab add_tsn."""
    if 'tsn' in env.roledefs.keys():
        execute("add_tsn_node", restart, env.host_string)

@task
def add_tsn_node(restart=True,*args):
    """Enable TSN functionality in particular node. USAGE: fab add_tsn_node."""

    restart = (str(restart).lower() == 'true')
    for host_string in args:
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
        cfgm_passwd = get_env_passwords(env.roledefs['cfgm'][0])
        compute_host = get_control_host_string(host_string)
        (tgt_ip, tgt_gw) = get_data_ip(host_string)
        compute_mgmt_ip= host_string.split('@')[1]
        compute_control_ip= hstr_to_ip(compute_host)
        admin_tenant_name = get_admin_tenant_name()

        # Check if nova-compute is allready running
        # Stop if running on TSN node
        with settings(host_string=host_string, warn_only=True):
            compute_hostname = sudo("hostname")
            if sudo("service nova-compute status | grep running").succeeded:
                # Stop the service
                sudo("service nova-compute stop")
                if detect_ostype() in ['ubuntu']:
                    sudo('echo "manual" >> /etc/init/nova-compute.override')
                else:
                    sudo('chkconfig nova-compute off')
                # Remove TSN node from nova manage service list
                # Mostly require when converting an exiting compute to TSN
                openstack_host = get_control_host_string(env.roledefs['openstack'][0])
                with settings(host_string=openstack_host, warn_only=True):
                    sudo("nova-manage service disable --host=%s --service=nova-compute" %(compute_hostname))
        admin_user, admin_password = get_authserver_credentials()
        authserver_ip = get_authserver_ip()
        with settings(host_string=env.roledefs['cfgm'][0], password=cfgm_passwd):
            prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                        "--admin_user %s --admin_password %s --admin_tenant_name %s --openstack_ip %s --router_type tor-service-node" \
                        %(compute_hostname, compute_control_ip, cfgm_ip,
                          admin_user, admin_password,
                          admin_tenant_name, authserver_ip)
            sudo("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))
        with settings(host_string=host_string, warn_only=True):
            nova_conf_file = '/etc/contrail/contrail-vrouter-agent.conf'
            sudo("openstack-config --set %s DEFAULT agent_mode tsn" % nova_conf_file)
            if restart:
                sudo("service supervisor-vrouter restart")

@hosts(get_toragent_nodes())
@task
def add_tor_agent(restart= True):
    """Add the tor agent nodes. Enable the compute nodes (mentioned with role toragent in testbed file) with tor agent functionality . USAGE: fab add_tor."""
    if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():
        execute("add_tor_agent_node", restart, env.host_string)

@task
def add_tor_agent_node(restart=True, *args):
    """Enable tor agent functionality in particular node. USAGE: fab add_tor_agent_node."""
    restart = (str(restart).lower() == 'true')
    for host_string in args:
        with settings(host_string=host_string):
            toragent_dict = getattr(env,'tor_agent', None)
            for i in range(len(toragent_dict[host_string])):
                execute("add_tor_agent_by_index", i, host_string, restart)

@task
def add_tor_agent_by_id(tid, node_info, restart=True):
    '''Enable tor agent functionality for a particular tor in particular node.
        USAGE: fab add_tor_agent_by_id:1,root@1.1.1.2
    '''
    host_string = node_info
    toragent_dict = getattr(env,'tor_agent', None)
    if not host_string in toragent_dict:
        print 'tor-agent entry for %s does not exist in testbed file' \
            %(host_string)
        return
    for i in range(len(toragent_dict[host_string])):
        tor_id= int(toragent_dict[host_string][i]['tor_id'])
        if int(tid) == tor_id:
            execute("add_tor_agent_by_index", i, host_string, restart)

@task
def add_tor_agent_by_index_range(range_str, host_string, restart=True):
    '''Enable tor agent functionality for a particular tor in particular node.
        USAGE: fab add_tor_agent_by_index_range:0-4,root@1.1.1.2
    '''
    if not is_tor_agent_index_range_valid(range_str, host_string):
       return
    range_array = range_str.split('-')
    for i in range(int(range_array[0]), (int(range_array[1]) + 1)):
        execute("add_tor_agent_by_index", i, host_string, restart)

@task
def add_tor_agent_by_index(index, node_info, restart=True):
    '''Enable tor agent functionality for a particular tor in particular node.
        USAGE: fab add_tor_agent_by_index:0,root@1.1.1.2
    '''
    i = int(index)
    host_string = node_info
    with settings(host_string=host_string):
        toragent_dict = getattr(env,'tor_agent', None)
        # Populate the argument to pass for setup-vnc-tor-agent
        tor_id = int(get_tor_agent_id(toragent_dict[host_string][i]))
        if tor_id == -1:
            return
        tor_name= toragent_dict[host_string][i]['tor_name']
        tor_tunnel_ip= toragent_dict[host_string][i]['tor_tunnel_ip']
        tor_vendor_name= toragent_dict[host_string][i]['tor_vendor_name']
        tor_product_name= ""
        if 'tor_product_name' in toragent_dict[host_string][i]:
            tor_product_name= toragent_dict[host_string][i]['tor_product_name']
        tsn_name=toragent_dict[host_string][i]['tor_tsn_name']
        tor_mgmt_ip=toragent_dict[host_string][i]['tor_ip']
        http_server_port = -1
        if 'tor_http_server_port' in toragent_dict[host_string][i]:
            http_server_port = toragent_dict[host_string][i]['tor_http_server_port']
        elif 'tor_agent_http_server_port' in toragent_dict[host_string][i]:
            http_server_port = toragent_dict[host_string][i]['tor_agent_http_server_port']
        if http_server_port == -1:
            print 'tor_agent_http_server_port configuration is missing in testbed file'
            return
        tgt_hostname = sudo("hostname")
        tor_agent_host = get_control_host_string(host_string)
        tor_agent_control_ip= hstr_to_ip(tor_agent_host)
        # Default agent name
        agent_name = tgt_hostname + '-' + str(tor_id)
        # If tor_agent_name is not specified or if its value is not
        # specified use default agent name
        tor_agent_name = ''
        if 'tor_agent_name' in toragent_dict[host_string][i]:
            tor_agent_name = toragent_dict[host_string][i]['tor_agent_name']
        if tor_agent_name != None:
            tor_agent_name = tor_agent_name.strip()
        if tor_agent_name == None or not tor_agent_name:
            tor_agent_name = agent_name

        # Default value for tor-agent ovsdb keepalive timer in millisec
        tor_agent_ovs_ka = '10000'
        if 'tor_agent_ovs_ka' in toragent_dict[host_string][i]:
            tor_agent_ovs_ka = toragent_dict[host_string][i]['tor_agent_ovs_ka']

        cmd = "setup-vnc-tor-agent"
        cmd += " --self_ip %s" % tor_agent_control_ip
        cmd += " --agent_name %s" % tor_agent_name
        cmd += " --http_server_port %s" % http_server_port
        cmd += " --tor_id %s" % tor_id
        cmd += " --tor_ip %s" % toragent_dict[host_string][i]['tor_ip']
        cmd += " --tor_ovs_port %s" % toragent_dict[host_string][i]['tor_ovs_port']
        cmd += " --tsn_ip %s" % toragent_dict[host_string][i]['tor_tsn_ip']
        cmd += " --tor_ovs_protocol %s" % toragent_dict[host_string][i]['tor_ovs_protocol']
        cmd += " --tor_agent_ovs_ka %s" % tor_agent_ovs_ka
        # HA arguments
        internal_vip = get_openstack_internal_vip()
        if internal_vip:
            # Highly availbale setup
            cmd += " --discovery_server_ip %s" % internal_vip
        else:
            cmd += " --discovery_server_ip %s" % hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
        # Execute the provision toragent script
        with cd(INSTALLER_DIR):
            sudo(cmd)
        # In SSL mode, create the SSL cert and private key files
        if toragent_dict[host_string][i]['tor_ovs_protocol'].lower() == 'pssl':
            domain_name = sudo("domainname -f")
            cert_file = "/etc/contrail/ssl/certs/tor." + str(tor_id) + ".cert.pem"
            privkey_file = "/etc/contrail/ssl/private/tor." + str(tor_id) + ".privkey.pem"
            # when we have HA configured for the agent, ensure that both
            # TOR agents use same SSL certificates. Copy the files
            # created on standby, if they are already created. Otherwise
            # generate the files.
            ssl_files_copied_from_standby = False
            standby_tor_idx, standby_host = get_standby_info(host_string, tor_name)
            if (standby_tor_idx != -1 and standby_host != None):
                ha_tor_id = str(get_tor_agent_id(toragent_dict[standby_host][standby_tor_idx]))
                cert_ha_file = '/etc/contrail/ssl/certs/tor.' + ha_tor_id + '.cert.pem'
                priv_ha_file = '/etc/contrail/ssl/private/tor.' + ha_tor_id + '.privkey.pem'
                temp_cert_file = tempfile.mktemp()
                temp_priv_file = tempfile.mktemp()
                with settings(host_string=standby_host):
                    if exists(cert_ha_file, use_sudo=True) and exists(priv_ha_file, use_sudo=True):
                        get_as_sudo(cert_ha_file, temp_cert_file)
                        get_as_sudo(priv_ha_file, temp_priv_file)
                if os.path.exists(temp_cert_file) and os.path.exists(temp_priv_file):
                    put(temp_cert_file, cert_file)
                    put(temp_priv_file, privkey_file)
                    os.remove(temp_cert_file)
                    os.remove(temp_priv_file)
                    ssl_files_copied_from_standby = True
            # Generate files if we didn't copy from standby
            if not ssl_files_copied_from_standby:
                ssl_cmd = "openssl req -new -x509 -days 3650 -text -sha256"
                ssl_cmd += " -newkey rsa:4096 -nodes -subj \"/C=US/ST=Global/O="
                ssl_cmd += tor_vendor_name + "/CN=" + domain_name + "\""
                ssl_cmd += " -keyout " + privkey_file + " -out " + cert_file
                sudo(ssl_cmd)

            # if CA cert file is specified, copy it to the target
            ca_cert_file = getattr(env, 'ca_cert_file', None)
            if ca_cert_file != None and os.path.isfile(ca_cert_file):
                put(ca_cert_file, '/etc/contrail/ssl/certs/cacert.pem')

        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
        cfgm_passwd = get_env_passwords(env.roledefs['cfgm'][0])
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
                     %(tor_agent_name, compute_control_ip, cfgm_ip,
                       admin_user, admin_password,
                       admin_tenant_name, keystone_ip)
        pr_args = "--device_name %s --vendor_name %s --device_mgmt_ip %s\
                   --device_tunnel_ip %s --device_tor_agent %s\
                   --device_tsn %s --api_server_ip %s --oper add\
                   --admin_user %s --admin_password %s\
                   --admin_tenant_name %s --openstack_ip %s"\
            %(tor_name, tor_vendor_name, tor_mgmt_ip,tor_tunnel_ip,
              tor_agent_name,tsn_name,cfgm_ip, admin_user, admin_password,
              admin_tenant_name, keystone_ip)
        if tor_product_name:
            pr_args += " --product_name %s" %(tor_product_name)
        with settings(host_string=env.roledefs['cfgm'][0], password=cfgm_passwd):
            sudo("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))
            sudo("python /opt/contrail/utils/provision_physical_device.py %s" %(pr_args))
        if restart:
            sudo("supervisorctl -c /etc/contrail/supervisord_vrouter.conf update")

@hosts(get_toragent_nodes())
@task
def delete_tor_agent(restart= True):
    '''Delete the tor agent nodes. Disable the compute nodes (mentioned with role
       toragent in testbed file) with tor agent functionality.
       USAGE: fab delete_tor_agent
    '''
    if 'toragent' in env.roledefs.keys() and 'tor_agent' in env.keys():
        execute("delete_tor_agent_node", restart, env.host_string)

@task
def delete_tor_agent_node(restart=True, *args):
    '''Disable tor agent functionality in particular node.
        USAGE: fab delete_tor_agent_node.
    '''
    restart = (str(restart).lower() == 'true')
    for host_string in args:
        with settings(host_string=host_string):
            toragent_dict = getattr(env,'tor_agent', None)
            for i in range(len(toragent_dict[host_string])):
                execute("delete_tor_agent_by_index", i, host_string, restart)

@task
def delete_tor_agent_by_id(tid, node_info, restart=True):
    '''Disable tor agent functionality for a particular tor in particular node.
        USAGE: fab delete_tor_agent_by_id:1,root@1.1.1.2
    '''
    host_string = node_info
    toragent_dict = getattr(env,'tor_agent', None)
    if not host_string in toragent_dict:
        print 'tor-agent entry for %s does not exist in testbed file' \
            %(host_string)
        return
    for i in range(len(toragent_dict[host_string])):
        tor_id= int(toragent_dict[host_string][i]['tor_id'])
        if int(tid) == tor_id:
            execute("delete_tor_agent_by_index", i, host_string, restart)

@task
def delete_tor_agent_by_index_range(range_str, host_string, restart=True):
    '''Disable tor agent functionality for a particular tor in particular node.
        USAGE: fab delete_tor_agent_by_index_range:0-4,root@1.1.1.2
    '''
    if not is_tor_agent_index_range_valid(range_str, host_string):
       return
    range_array = range_str.split('-')
    for i in range(int(range_array[0]), (int(range_array[1]) + 1)):
        execute("delete_tor_agent_by_index", i, host_string, restart)

@task
def delete_tor_agent_by_index(index, node_info, restart=True):
    '''Disable tor agent functionality in particular node.
        USAGE: fab delete_tor_agent_by_index:0,root@1.1.1.2
    '''
    i = int(index)
    host_string = node_info
    with settings(host_string=host_string):
        toragent_dict = getattr(env,'tor_agent', None)
        if not host_string in toragent_dict:
            print 'tor-agent entry for %s does not exist in testbed file' \
                %(host_string)
            return
        if not i < len(toragent_dict[host_string]):
            print 'tor-agent entry for host %s and index %d does not exist in '\
                'testbed file' %(host_string, i)
            return
        # Populate the argument to pass for setup-vnc-tor-agent
        tor_id = int(get_tor_agent_id(toragent_dict[host_string][i]))
        if tor_id == -1:
            return
        tor_name= toragent_dict[host_string][i]['tor_name']
        tor_vendor_name= toragent_dict[host_string][i]['tor_vendor_name']
        tgt_hostname = sudo("hostname")
        # Default agent name
        agent_name = tgt_hostname + '-' + str(tor_id)
        # If tor_agent_name is not specified or if its value is not
        # specified use default agent name
        tor_agent_name = ''
        if 'tor_agent_name' in toragent_dict[host_string][i]:
            tor_agent_name = toragent_dict[host_string][i]['tor_agent_name']
        if tor_agent_name != None:
            tor_agent_name = tor_agent_name.strip()
        if tor_agent_name == None or not tor_agent_name:
            tor_agent_name = agent_name

        # Stop tor-agent process
        tor_process_name = 'contrail-tor-agent-' + str(tor_id)
        cmd = 'service ' + tor_process_name + ' stop'
        sudo(cmd)

        # Remove tor-agent config file
        tor_file_name = '/etc/contrail/' + tor_process_name + '.conf'
        if exists(tor_file_name, use_sudo=True):
            remove_file(tor_file_name)
        # Remove tor-agent INI file used by supervisord
        tor_ini_file_name = '/etc/contrail/supervisord_vrouter_files/' + tor_process_name + '.ini'
        if exists(tor_ini_file_name, use_sudo=True):
            remove_file(tor_ini_file_name)

        # Remove tor-agent init file
        tor_init_file = '/etc/init.d/' + tor_process_name
        if exists(tor_init_file, use_sudo=True):
            remove_file(tor_init_file)

        # If SSL files generated for tor-agent exists, remove them
        cert_file = "/etc/contrail/ssl/certs/tor." + str(tor_id) + ".cert.pem"
        privkey_file = "/etc/contrail/ssl/private/tor." + str(tor_id) + ".privkey.pem"
        if exists(cert_file, use_sudo=True):
            remove_file(cert_file)
        if exists(privkey_file, use_sudo=True):
            remove_file(privkey_file)
        if exists('/etc/contrail/ssl/certs/cacert.pem', use_sudo=True):
            remove_file('/etc/contrail/ssl/certs/cacert.pem')

        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = get_env_passwords(env.roledefs['cfgm'][0])
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        cfgm_user = env.roledefs['cfgm'][0].split('@')[0]
        cfgm_passwd = get_env_passwords(env.roledefs['cfgm'][0])
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
        prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper del " \
                    "--admin_user %s --admin_password %s --admin_tenant_name %s\
                     --openstack_ip %s" \
                     %(tor_agent_name, compute_control_ip, cfgm_ip, admin_user,
                       admin_password, admin_tenant_name, keystone_ip)
        pr_args = "--device_name %s --vendor_name %s --api_server_ip %s\
                   --oper del --admin_user %s --admin_password %s\
                   --admin_tenant_name %s --openstack_ip %s"\
            %(tor_name, tor_vendor_name, cfgm_ip, admin_user, admin_password,
              admin_tenant_name, keystone_ip)
        with settings(host_string=env.roledefs['cfgm'][0], password=cfgm_passwd):
            sudo("python /opt/contrail/utils/provision_physical_device.py %s" %(pr_args))
            sudo("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))
        if restart:
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
        execute('increase_ulimits')
        execute('setup_openstack')
        if get_openstack_internal_vip():
            execute('sync_keystone_ssl_certs')
        execute('verify_openstack')
    #setup_vcenter can be called outside of setup_all and need not be below. So commenting.
    #elif orch == 'vcenter':
        #execute('setup_vcenter')

@roles('build')
@task
def join_cluster(new_ctrl_ip):
    """Provisions required contrail services in the node as per the role definition.
    """
    execute('setup_common_node', new_ctrl_ip)
    execute('join_ha_cluster', new_ctrl_ip)


@task
@roles('compute')
def setup_vm_coremask(q_coremask=False):
    """
    On all nodes setup CPU affinity for QEMU processes based on vRouter/DPDK
    core affinity or q_coremask argument.
    """
    if env.roledefs['compute']:
        execute("setup_vm_coremask_node", q_coremask, env.host_string)

@task
def setup_vm_coremask_node(q_coremask, *args):
    """
    Setup CPU affinity for QEMU processes based on vRouter/DPDK core affinity
    on a given node.

    Supported core mask format:
        vRouter/DPDK:   hex (0x3f), list (0,1,2,3,4,5), range (0,3-5)
        QEMU/nova.conf: list (0,1,2,3,4,5), range (0,3-5), exclusion (0-5,^4)

    QEMU needs to be pinned to different cores than vRouter. Because of
    different core mask formats, it is not possible to just set QEMU to
    <not vRouter cores>. This function takes vRouter core mask from testbed,
    changes it to list of cores and removes them from list of all possible
    cores (generated as a list from 0 to N-1, where N = number of cores).
    This is changed back to string and passed to openstack-config.
    """
    vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'

    for host_string in args:
        dpdk = getattr(env, 'dpdk', None)
        if dpdk:
            if env.host_string in dpdk:
                try:
                    vr_coremask = dpdk[env.host_string]['coremask']
                except KeyError:
                    raise RuntimeError("vRouter core mask for host %s is not defined." \
                        %(host_string))
            else:
                print "No %s in the dpdk section in testbed file." \
                    %(env.host_string)
                return
        else:
            print "No dpdk section in testbed file on host %s." %(env.host_string)
            return

        if not vr_coremask:
            raise RuntimeError("Core mask for host %s is not defined." \
                % host_string)

        if not q_coremask:
            all_cores = [x for x in xrange(cpu_count())]

            if 'x' in vr_coremask:  # String containing hexadecimal mask.
                vr_coremask = int(vr_coremask, 16)

                """
                Convert hexmask to a string with numbers of cores to be used, eg.
                0x19 -> 11001 -> 10011 -> [(0,1), (1,0), (2,0), (3,1), (4,1)] -> '0,3,4'
                """
                vr_coremask = [x[0] for x in enumerate(reversed(bin(vr_coremask)[2:])) if x[1] == '1']
            elif (',' in vr_coremask) or ('-' in vr_coremask):  # Range or list of cores.
                vr_coremask = vr_coremask.split(',')  # Get list of core numbers and/or core ranges.

                # Expand ranges like 0-4 to 0, 1, 2, 3, 4.
                vr_coremask_expanded = []
                for rng in vr_coremask:
                    if '-' in rng:  # If it's a range - expand it.
                        a, b = rng.split('-')
                        vr_coremask_expanded += range(int(a), int(b)+1)
                    else:  # If not, just add to the list.
                        vr_coremask_expanded.append(int(rng))

                vr_coremask = vr_coremask_expanded
            else:  # A single core.
                try:
                    single_core = int(vr_coremask)
                except ValueError:
                    raise RuntimeError("Error: vRouter core mask %s for host %s is invalid." \
                        %(vr_coremask, host_string))

                vr_coremask = []
                vr_coremask.append(single_core)

            # From list of all cores remove list of vRouter cores and stringify.
            diff = set(all_cores) - set(vr_coremask)
            q_coremask = ','.join(str(x) for x in diff)

        with settings(host_string=host_string):
            # This can fail eg. because openstack-config is not present.
            # There's no sanity check in openstack-config.
            if sudo("openstack-config --set /etc/nova/nova.conf DEFAULT vcpu_pin_set %s" \
                % q_coremask).succeeded:
                print "QEMU coremask on host %s set to %s." \
                    %(env.host_string, q_coremask)
            else:
                raise RuntimeError("Error: setting QEMU core mask %s for host %s failed." \
                    %(vr_coremask, host_string))

@roles('build')
@task
def setup_all(reboot='True'):
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute('setup_common')
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('increase_limits')
    execute('setup_database')
    execute('verify_database')
    execute('fixup_mongodb_conf')
    execute('setup_mongodb_ceilometer_cluster')
    execute('setup_orchestrator')
    execute('setup_cfgm')
    execute('verify_cfgm')
    execute('setup_control')
    execute('verify_control')
    execute('setup_collector')
    execute('verify_collector')
    execute('setup_webui')
    execute('verify_webui')
    if 'vcenter_compute' in env.roledefs:
        execute('setup_vcenter_compute')
    execute('setup_vrouter')
    execute('prov_config_node')
    execute('prov_database_node')
    execute('prov_analytics_node')
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    execute('add_tsn', restart=False)
    execute('add_tor_agent', restart=False)
    execute('increase_vrouter_limit')
    execute('setup_vm_coremask')
    if get_openstack_internal_vip():
        execute('setup_cluster_monitors')
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
    execute('prov_config')
    execute('prov_database')
    execute('prov_analytics')
    execute('prov_control_bgp')
    execute('prov_external_bgp')
    execute('prov_metadata_services')
    execute('prov_encap_type')
    execute('setup_remote_syslog')
    execute('add_tsn', restart=False)
    execute('add_tor_agent', restart=False)
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
    execute('increase_limits_no_control')
    execute('setup_database')
    execute('verify_database')
    execute('setup_cfgm')
    execute('verify_cfgm')
    execute('setup_collector')
    execute('verify_collector')
    execute('setup_webui')
    execute('verify_webui')
    execute('prov_config')
    execute('prov_database')
    execute('prov_analytics')
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
        execute(increase_limits)
        execute(increase_ulimits)
        execute(setup_database)
        execute(verify_database)
        execute(fixup_mongodb_conf)
        execute(setup_mongodb_ceilometer_cluster)
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
        execute(add_tsn)
        execute(add_tor_agent)
        execute('increase_vrouter_limit')
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
    execute(compute_reboot)
#end reset_config

@task
def create_contrailvm(host_list, host_string, esxi_info, vcenter_info):
    host = ""
    # find the esxi host given hostip from the esxi_info
    for x in host_list:
        if esxi_info[x]['ip'] == host_string:
            host = x
    if not host:
        print "No op for esxi host -- %s" %env.host_string
        return

    if host in esxi_info.keys():
         mode = get_mode(esxi_info[host]['contrail_vm']['host'])
         if mode == 'openstack':
             std_switch = True
             power_on = True
         if mode == 'vcenter':
             if 'fabric_vswitch' in esxi_info[host].keys():
                 std_switch = True
                 power_on = True
             elif ('pci_devices' in esxi_info[host]['contrail_vm']) and \
                  ('nic' in esxi_info[host]['contrail_vm']['pci_devices']):
                 std_switch = True
                 power_on = False
             elif 'dv_switch_fab' in vcenter_info.keys():
                 std_switch = False
                 power_on = False
             else:
                 std_switch = True
                 power_on = True
         if (std_switch == True):
             apply_esxi_defaults(esxi_info[host])
             configure_esxi_network(esxi_info[host])
         else:
             apply_esxi_defaults(esxi_info[host])
             esxi_info[host]['fabric_vswitch'] = None
         create_esxi_compute_vm(esxi_info[host], vcenter_info, power_on)
    else:
         print 'Info: esxi_hosts block does not have the esxi host.Exiting'
# end create_contrailvm

@task
@parallel(pool_size=20)
@hosts([h['ip'] for h in getattr(testbed, 'esxi_hosts', {}).values()])
def prov_esxi_task(host_list, esxi_info, vcenter_info):
    execute(create_contrailvm, host_list, env.host_string, esxi_info, vcenter_info)
#end prov_esxi_task

@task
@roles('build')
def prov_esxi(*args):
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return
    if args:
        host_list = args
    else:
        host_list = esxi_info.keys()

    orch = get_orchestrator()
    if orch == 'vcenter' or 'vcenter_compute' in env.roledefs:
        vcenter_info = getattr(env, 'vcenter', None)
        if not vcenter_info:
            print 'Info: vcenter_server block is not defined in testbed file.Exiting'
            return
    else:
        vcenter_info = None

    execute(prov_esxi_task, host_list, esxi_info, vcenter_info)

    dv_switch_fab = False
    pci_fab = False
    for h in host_list:
        mode = get_mode(esxi_info[h]['contrail_vm']['host'])
        if mode == 'vcenter':
            vcenter_info = getattr(env, 'vcenter', None)
            if not vcenter_info:
                print 'Info: vcenter block is not defined in testbed file.Exiting'
                return
            if 'fabric_vswitch' in esxi_info[h].keys():
                std_switch = True
            elif ('pci_devices' in esxi_info[h]['contrail_vm']) and \
                 ('nic' in esxi_info[h]['contrail_vm']['pci_devices']):
                pci_fab = True
            elif 'dv_switch_fab' in vcenter_info.keys():
                esxi_info[h]['fabric_vswitch'] = None
                dv_switch_fab = True
            else:
                std_switch = True
    sleep(20)
    if (dv_switch_fab == True):
         provision_dvs_fab(vcenter_info, esxi_info, host_list)
    if (pci_fab == True):
        role_info = getattr(env, 'roledefs', None)
        compute_list = role_info['compute']
        password_list = getattr(env, 'passwords', None)
        bond_list = getattr(testbed, 'bond', None)
        provision_pci_fab(vcenter_info, esxi_info, host_list, compute_list, password_list, bond_list)
    if orch == 'vcenter' or 'vcenter_compute' in env.roledefs:
         provision_vcenter_features(vcenter_info, esxi_info, host_list)

@task
def update_esxi_vrouter_map():
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    for host_string in env.roledefs['cfgm']:
        with settings(host_string=host_string):
            tmp_fname = "/tmp/ESXiToVRouterIp-%s" %(env.host_string)
            for esxi_host in esxi_info:
                esxi_ip = esxi_info[esxi_host]['ip']
                vrouter_ip_string = esxi_info[esxi_host]['contrail_vm']['host']
                vrouter_ip = hstr_to_ip(vrouter_ip_string)
                local("echo '%s:%s' >> %s" %(esxi_ip, vrouter_ip, tmp_fname))
            put(tmp_fname, "/etc/contrail/ESXiToVRouterIp.map", use_sudo=True)
            local("rm %s" %(tmp_fname))
            sudo("service contrail-vcenter-plugin restart")

@task
def prov_vcenter_datastores():
    vcenter_info = getattr(env, 'vcenter', None)
    if not vcenter_info:
        return
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Error: esxi_hosts block is not defined in testbed file.Exiting'
        return
    for esx in esxi_info:
        host = esxi_info[esx]
        host_string = host['username'] + '@' +  host['ip']
        ds = os.path.split(host['datastore'])
        if not ds[1]:
            ds = os.path.split(ds[0])
        old_ds = 'datastore1'
        if old_ds == ds[1]:
            print 'Old and New names for datastore are same, skipping'
            continue
        new_ds = os.path.join(ds[0], ds[1])
        ds = ds[0]
        print 'renaming %s to %s' % (old_ds, new_ds)
        with settings(host_string=host_string, password=host['password'],
                      shell = '/bin/sh -l -c'):
            run("ln -s `ls -l %s | grep %s | awk '{print $11}` %s" % (ds, old_ds, new_ds))

@hosts(env.roledefs['cfgm'][0])
@task
def cleanup_vcenter():
    vcenter_info = getattr(env, 'vcenter', None)
    if not vcenter_info:
        print 'Error: vcenter block is not defined in testbed file.Exiting'
        return
    deprovision_vcenter(vcenter_info)

@hosts(env.roledefs['cfgm'][0])
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
    role_info = getattr(env, 'roledefs', None)
    compute_list = role_info['compute']
    password_list = getattr(env, 'passwords', None)
    (hosts, clusters, vms) = get_esxi_vms_and_hosts(esxi_info, vcenter_info, host_list, compute_list, password_list)
    provision_vcenter(vcenter_info, hosts, clusters, vms, 'True')
    update_esxi_vrouter_map()

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
    role_info = getattr(env, 'roledefs', None)
    compute_list = role_info['compute']
    password_list = getattr(env, 'passwords', None)
    (hosts, clusters, vms) = get_esxi_vms_and_hosts(esxi_info, vcenter_info, host_list, compute_list, password_list)
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
        vlan = get_vlan_tag(device, tgt_host)
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


@task
def dpdk_increase_vrouter_limit():
    """Increase the maximum number of mpls label and nexthop on tsn node"""
    vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'
    vrouter_module_params_dict = getattr(env, 'vrouter_module_params', None)
    if vrouter_module_params_dict:
        for host_string in vrouter_module_params_dict:
             cmd = "--vr_mpls_labels %s " % vrouter_module_params_dict[host_string].setdefault('mpls_labels', '5120')
             cmd += "--vr_nexthops %s " % vrouter_module_params_dict[host_string].setdefault('nexthops', '65536')
             cmd += "--vr_vrfs %s " % vrouter_module_params_dict[host_string].setdefault('vrfs', '5120')
             cmd += "--vr_bridge_entries %s " % vrouter_module_params_dict[host_string].setdefault('macs', '262144')
             with settings(host_string=host_string, warn_only=True):
                 sudo('sed -i \'s#\(^command=.*$\)#\\1 %s#\' %s'\
                         %(cmd, vrouter_file))
# end dpdk_increase_vrouter_limit();


import string
import textwrap
import json

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.utils.migration import *
from fabfile.utils.storage import *
from fabfile.utils.analytics import *
from fabfile.tasks.install import *
from fabfile.tasks.verify import *
from fabfile.tasks.helpers import *
from fabfile.tasks.tester import setup_test_env
from fabfile.tasks.rabbitmq import setup_rabbitmq_cluster
from fabfile.tasks.vmware import configure_esxi_network, create_ovf
from time import sleep
from fabric.contrib.files import exists

@task
@EXECUTE_TASK
@roles('all')
def bash_autocomplete_systemd():
    host = env.host_string
    output = run('uname -a')
    if 'xen' in output or 'el6' in output or 'Ubuntu' in output:
        pass
    else:
        #Assume Fedora
        sudo("echo 'source /etc/bash_completion.d/systemd-bash-completion.sh' >> /root/.bashrc")

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
    timeout server 48h"""
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
            get("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-config-marker-start/,/^#contrail-config-marker-end/d' %s" %(tmp_fname))
                local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" %(tmp_fname))
            # ...generate new ones
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(haproxy_config)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg")
            local("rm %s" %(tmp_fname))
            
        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            run("chkconfig haproxy on")
            run("service haproxy restart")

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
        get("/etc/haproxy/haproxy.cfg", tmp_fname)
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
        put(tmp_fname, "/etc/haproxy/haproxy.cfg")
        local("rm %s" %(tmp_fname))

        # enable
        with settings(host_string=compute_host_string, warn_only=True):
            run("chkconfig haproxy on")
            run("service haproxy restart")

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
            get("/etc/haproxy/haproxy.cfg", tmp_fname)
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
            put(tmp_fname, "/etc/haproxy/haproxy.cfg")
            local("rm %s" %(tmp_fname))

            # enable
            with settings(host_string=openstack_host_string, warn_only=True):
                run("chkconfig haproxy on")
                run("service haproxy restart")

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
        #qpidd_changes_for_ubuntu()
        #cfgm_host = env.host_string
        cfgm_host=get_control_host_string(host_string)
        tgt_ip = hstr_to_ip(cfgm_host)
        cfgm_host_password = env.passwords[host_string]

        openstack_admin_password = get_keystone_admin_password()
        keystone_ip = get_keystone_ip()

        # Prefer local collector node
        cfgm_host_list=[]
        for entry in env.roledefs['cfgm']:
            cfgm_host_list.append(get_control_host_string(entry))
        if cfgm_host in cfgm_host_list:
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
        with  settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisor-config.override')
                    run('rm /etc/init/neutron-server.override')
            cmd = "PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-cfgm.py --self_ip %s --keystone_ip %s --collector_ip %s %s --cassandra_ip_list %s --zookeeper_ip_list %s --quantum_port %s --nworkers %d --keystone_auth_protocol %s --keystone_auth_port %s --keystone_admin_token %s --keystone_insecure %s %s %s %s --amqp_server_ip %s" %(
                 cfgm_host_password,
                 openstack_admin_password,
                 tgt_ip,
                 keystone_ip,
                 collector_ip,
                 mt_opt,
                 ' '.join(cassandra_ip_list),
                 ' '.join(cassandra_ip_list),
                 quantum_port,
                 nworkers,
                 get_keystone_auth_protocol(),
                 get_keystone_auth_port(),
                 get_keystone_admin_token(),
                 get_keystone_insecure_flag(),
                 get_service_token_opt(),
                 get_haproxy_opt(),
                 get_region_name_opt(),
                 amqp_server_ip)
            internal_vip = get_contrail_internal_vip()
            if internal_vip:
                cmd += ' --internal_vip %s' % (internal_vip)
            manage_neutron = get_manage_neutron()
            if manage_neutron == 'no':
                cmd += ' --manage_neutron %s' % manage_neutron
            with cd(INSTALLER_DIR):
                run(cmd)

    # HAPROXY fixups
    fixup_restart_haproxy_in_all_cfgm(nworkers)
    haproxy = get_haproxy_opt()
    if haproxy:
        fixup_restart_haproxy_in_all_compute()
        fixup_restart_haproxy_in_all_openstack()
#end setup_cfgm_node

@task
@roles('openstack')
def setup_openstack():
    """Provisions openstack services in all nodes defined in openstack role."""
    execute('add_openstack_reserverd_ports')
    if env.roledefs['openstack']:
        execute("setup_openstack_node", env.host_string)
        # Blindly run setup_openstack twice for Ubuntu
        #TODO Need to remove this finally
        if detect_ostype() == 'Ubuntu':
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
        cmd = "PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-openstack.py --self_ip %s --keystone_ip %s --cfgm_ip %s --keystone_auth_protocol %s --amqp_server_ip %s --quantum_service_protocol %s %s %s" %(
                    openstack_host_password, openstack_admin_password, self_ip, keystone_ip, cfgm_ip, get_keystone_auth_protocol(), amqp_server_ip, get_quantum_service_protocol(), get_service_token_opt(), get_haproxy_opt())
        cmd += ' --openstack_index %s' % (env.roledefs['openstack'].index(host_string) + 1)
        if internal_vip:
            openstack_ip_list = ' '.join([hstr_to_ip(openstack_host) for openstack_host in env.roledefs['openstack']])
            cmd += ' --internal_vip %s' % (internal_vip)
            cmd += ' --mgmt_self_ip %s' % mgmt_self_ip
        contrail_internal_vip = get_contrail_internal_vip()
        if contrail_internal_vip:
            cmd += ' --contrail_internal_vip %s' % (contrail_internal_vip)
        if openstack_ip_list:
            cmd += ' --openstack_ip_list %s' % openstack_ip_list
        with  settings(host_string=host_string):
            with cd(INSTALLER_DIR):
                run(cmd)
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
    if detect_ostype() == 'Ubuntu':
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
            hash_key = run("grep 'def hash_key' %s" % file_name).succeeded
        if not hash_key:
            # Add a hash generating function
            run('sed -i "/^SECRET_KEY.*/a\    return new_key" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\        new_key = m.hexdigest()" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\        m.update(new_key)" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\        m = hashlib.md5()" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\    if len(new_key) > 250:" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\    new_key = \':\'.join([key_prefix, str(version), key])" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\def hash_key(key, key_prefix, version):" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\import hashlib" %s' % file_name)
            run('sed -i "/^SECRET_KEY.*/a\# To ensure key size of 250" %s' % file_name)
        run("sed  -i \"s/'LOCATION' : '127.0.0.1:11211',/'LOCATION' : '%s:11211',/\" %s" % (hstr_to_ip(env.host_string), file_name))
        with settings(warn_only=True):
            if run("grep '\'KEY_FUNCTION\': hash_key,' %s" % file_name).failed:
                run('sed -i "/\'LOCATION\'.*/a\       \'KEY_FUNCTION\': hash_key," %s' % file_name)
        run("sed -i -e 's/OPENSTACK_HOST = \"127.0.0.1\"/OPENSTACK_HOST = \"%s\"/' %s" % (internal_vip,file_name))

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
                if detect_ostype() == 'Ubuntu':
                    run("service redis-server stop")
                    run("sed -i -e '/^[ ]*bind/s/^/#/' /etc/redis/redis.conf")
                    run("service redis-server start")
                else:
                    run("service redis stop")
                    run("sed -i -e '/^[ ]*bind/s/^/#/' /etc/redis.conf")
                    run("chkconfig redis on")
                    run("service redis start")
        
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
        with  settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisor-analytics.override')
            with cd(INSTALLER_DIR):
                # Release from contrail-install-packages
                rls = get_release()
                # Bitbucket - Redis UVE master slave
                if '1.04' in rls: 
                    run_cmd = "PASSWORD=%s python setup-vnc-collector.py --cassandra_ip_list %s --cfgm_ip %s --self_collector_ip %s --num_nodes %d --redis_master_ip %s --redis_role " \
                           % (collector_host_password, ' '.join(cassandra_ip_list), cfgm_ip, tgt_ip, ncollectors, redis_master_ip) 
                    if not is_redis_master:
                        run_cmd += "slave "
                    else:
                        run_cmd += "master "
                else:
                    # Github - Independent Redis UVE and Syslog
                    run_cmd = "PASSWORD=%s python setup-vnc-collector.py --cassandra_ip_list %s --cfgm_ip %s --self_collector_ip %s --num_nodes %d " \
                           % (collector_host_password, ' '.join(cassandra_ip_list), cfgm_ip, tgt_ip, ncollectors) 
                    analytics_syslog_port = get_collector_syslog_port()
                    if analytics_syslog_port is not None:
                        run_cmd += "--analytics_syslog_port %d " % (analytics_syslog_port)
                analytics_database_ttl = get_database_ttl()
                if analytics_database_ttl is not None:
                    run_cmd += "--analytics_data_ttl %d " % (analytics_database_ttl)
                else:
                    #if nothing is provided we default to 48h
                    run_cmd += "--analytics_data_ttl 48 "
                internal_vip = get_contrail_internal_vip()
                if internal_vip:
                    run_cmd += " --internal_vip %s" % internal_vip
                print run_cmd
                run(run_cmd)
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
        database_host_list=[]
        for entry in env.roledefs['database']:
            database_host_list.append(get_control_host_string(entry))
        zookeeper_ip_list = [hstr_to_ip(get_control_host_string(zookeeper_host)) for zookeeper_host in env.roledefs['database']]
        database_host=get_control_host_string(host_string)
        database_host_password=env.passwords[host_string]
        tgt_ip = hstr_to_ip(database_host)
        with  settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisord-contrail-database.override')
            with cd(INSTALLER_DIR):
                run_cmd = "PASSWORD=%s python setup-vnc-database.py --self_ip %s --cfgm_ip %s " % (database_host_password, tgt_ip, cfgm_ip)
                database_dir = get_database_dir()
                if database_dir is not None:
                    run_cmd += "--data_dir %s " % (database_dir)
                analytics_data_dir = get_analytics_data_dir()
                if analytics_data_dir is not None:
                    run_cmd += "--analytics_data_dir %s " % (analytics_data_dir)
                ssd_data_dir = get_ssd_data_dir()
                if ssd_data_dir is not None:
                    run_cmd += "--ssd_data_dir %s " % (ssd_data_dir)
                if (len(env.roledefs['database'])>2):
                    run_cmd += "--seed_list %s,%s" % (hstr_to_ip(get_control_host_string(env.roledefs['database'][0])),hstr_to_ip(get_control_host_string(env.roledefs['database'][1])))
                else: 
                    run_cmd += "--seed_list %s" % (hstr_to_ip(get_control_host_string(env.roledefs['database'][0])))
                run_cmd += " --zookeeper_ip_list %s" % ' '.join(zookeeper_ip_list)
                run_cmd += " --database_index %d" % (database_host_list.index(database_host) + 1)
                run(run_cmd)
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
        openstack_host = get_control_host_string(env.roledefs['openstack'][0])
        openstack_ip = hstr_to_ip(openstack_host)
        keystone_ip = get_keystone_ip()
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
        with  settings(host_string=host_string):
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisor-webui.override')
            cmd = "PASSWORD=%s python setup-vnc-webui.py --cfgm_ip %s --keystone_ip %s --openstack_ip %s --collector_ip %s --cassandra_ip_list %s" %(cfgm_host_password, cfgm_ip, keystone_ip, openstack_ip, collector_ip, ' '.join(cassandra_ip_list))
            internal_vip = get_contrail_internal_vip()
            if internal_vip:
                cmd += " --internal_vip %s" % internal_vip
            contrail_internal_vip = get_contrail_internal_vip()
            if contrail_internal_vip:
                cmd += " --contrail_internal_vip %s" % contrail_internal_vip
            with cd(INSTALLER_DIR):
                run(cmd)
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
            if detect_ostype() == 'Ubuntu':
                pfl = "/etc/ifmap-server/basicauthusers.properties"
            else:
                pfl = "/etc/irond/basicauthusers.properties"
            # replace control-node and dns proc creds
            run("sed -i -e '/%s:/d' -e '/%s.dns:/d' %s" \
                      %(control_ip, control_ip, pfl))
            run("echo '%s:%s' >> %s" \
                         %(control_ip, control_ip, pfl))
            run("echo '%s.dns:%s.dns' >> %s" \
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
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisor-control.override')
                    run('rm /etc/init/supervisor-dns.override')
            with cd(INSTALLER_DIR):
                run("PASSWORD=%s python setup-vnc-control.py --self_ip %s --cfgm_ip %s --collector_ip %s" \
                     %(cfgm_host_password, tgt_ip, cfgm_ip, collector_ip))
                if detect_ostype() == 'centos':
                    run("PASSWORD=%s service contrail-control restart" % cfgm_host_password, pty=False)
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
                    out = run("grep flow_cache_timeout %s" %(agent_conf_file))
                    run("sed -i \"s|%s|%s|\" %s" %(out, flow_cache_set_cmd, agent_conf_file))
                    run("grep flow_cache_timeout %s" %(agent_conf_file))
        except Exception:
            pass

    # Set per_vm_flow_limit as %, default is 100...
    for host_string in args:
        try:
            if (getattr(env, 'max_vm_flows', None)):
                max_vm_flows_set_cmd = "max_vm_flows=%s" %(env.max_vm_flows)
                restart_service = True
                with settings(host_string=host_string):
                    out = run("grep max_vm_flows %s" %(agent_conf_file))
                    run("sed -i \"s|%s|%s|\" %s" %(out, max_vm_flows_set_cmd, agent_conf_file))
                    run("grep max_vm_flows %s" %(agent_conf_file))
        except Exception:
            pass

    # After setting all agent parameters, restart service...
    if restart_service:
        for host_string in args:
            with settings(host_string=host_string):
                out = run("service supervisor-vrouter restart")

# end setup_agent_config_in_node

@task
@EXECUTE_TASK
@roles('compute')
def setup_vrouter(manage_nova_compute='yes'):
    """Provisions vrouter services in all nodes defined in vrouter role.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
    """
    if env.roledefs['compute']:
       execute("setup_only_vrouter_node", manage_nova_compute,  env.host_string)

@task
def setup_vrouter_node(*args):
    """Provisions nova-compute and vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2"""
    execute("setup_only_vrouter_node", 'yes', *args)

@task
def setup_only_vrouter_node(manage_nova_compute='yes', *args):
    """Provisions only vrouter services in one or list of nodes. USAGE: fab setup_vrouter_node:user@1.1.1.1,user@2.2.2.2
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute provisioning will be skipped.
    """
    # make sure an agent pkg has been installed
    #try:
    #    run("yum list installed | grep contrail-agent")
    #except SystemExit as e:
    #    print "contrail-agent package not installed. Install it and then run setup_vrouter"
    #    return
    
    
    for host_string in args:
        # Enable haproxy for Ubuntu
        with  settings(host_string=host_string):
            enable_haproxy()
        #qpidd_changes_for_ubuntu()
        ncontrols = len(env.roledefs['control'])
        cfgm_host = get_control_host_string(env.roledefs['cfgm'][0])
        cfgm_host_password = env.passwords[env.roledefs['cfgm'][0]]
        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
        openstack_mgmt_ip = hstr_to_ip(env.roledefs['openstack'][0])
        keystone_ip = get_keystone_ip()
        ks_auth_protocol = get_keystone_auth_protocol()
        ks_auth_port = get_keystone_auth_port()
        compute_host = get_control_host_string(host_string)
        (tgt_ip, tgt_gw) = get_data_ip(host_string)
    
        compute_mgmt_ip= host_string.split('@')[1]
        compute_control_ip= hstr_to_ip(compute_host)

        # Check and configure the VGW details
        set_vgw= 0
        if 'vgw' in env.roledefs:
            if host_string in env.roledefs['vgw']:
                set_vgw = 1
                vgw_intf_list = env.vgw[host_string].keys()
                public_subnet = []
                public_vn_name = []
                gateway_routes = []
                for vgw_intf in vgw_intf_list:
                    public_subnet.append(env.vgw[host_string][vgw_intf]['ipam-subnets'])
                    public_vn_name.append(env.vgw[host_string][vgw_intf]['vn'])
                    if 'gateway-routes' in env.vgw[host_string][vgw_intf].keys():
                        gateway_routes.append(env.vgw[host_string][vgw_intf]['gateway-routes'])
                    else:
                        gateway_routes.append("[]")
                gateway_routes = str([(';'.join(str(e) for e in gateway_routes)).replace(" ","")])
                public_subnet = str([(';'.join(str(e) for e in public_subnet)).replace(" ","")])
                public_vn_name = str([(';'.join(str(e) for e in public_vn_name)).replace(" ","")])
                vgw_intf_list = str([(';'.join(str(e) for e in vgw_intf_list)).replace(" ","")])
        haproxy = get_haproxy_opt()
        if haproxy:
            # setup haproxy and enable
            fixup_restart_haproxy_in_one_compute(host_string)
    
        openstack_admin_password = get_keystone_admin_password()
        amqp_server_ip = ' '.join([hstr_to_ip(get_control_host_string(cfgm_host)) for cfgm_host in env.roledefs['cfgm']])
        if get_from_testbed_dict('openstack','manage_amqp', 'no') == 'yes':
            amqp_server_ip = ' '.join([hstr_to_ip(get_control_host_string(openstack_host)) for openstack_host in env.roledefs['openstack']])

        with  settings(host_string=host_string):
            vmware = False
            compute_vm_info = getattr(testbed, 'compute_vm', None)
            if compute_vm_info:
                hosts = compute_vm_info.keys()
                if host_string in hosts:
                    vmware = True
                    vmware_info = compute_vm_info[host_string]
            if detect_ostype() == 'Ubuntu':
                with settings(warn_only=True):
                    run('rm /etc/init/supervisor-vrouter.override')
            with cd(INSTALLER_DIR):
                cmd= "PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-vrouter.py --self_ip %s --cfgm_ip %s --keystone_ip %s --openstack_mgmt_ip %s --ncontrols %s --keystone_auth_protocol %s --keystone_auth_port %s --amqp_server_ip_list %s --quantum_service_protocol %s %s %s" \
                         %(cfgm_host_password, openstack_admin_password, compute_control_ip, cfgm_ip, keystone_ip, openstack_mgmt_ip, ncontrols, ks_auth_protocol, ks_auth_port, amqp_server_ip, get_quantum_service_protocol(), get_service_token_opt(), haproxy)
                if tgt_ip != compute_mgmt_ip: 
                    cmd = cmd + " --non_mgmt_ip %s --non_mgmt_gw %s" %( tgt_ip, tgt_gw )
                if set_vgw:   
                    cmd = cmd + " --public_subnet %s --public_vn_name %s --vgw_intf %s" %(public_subnet,public_vn_name,vgw_intf_list)
                    if gateway_routes != []:
                        cmd = cmd + " --gateway_routes %s" %(gateway_routes)
                if vmware:
                    cmd = cmd + " --vmware %s --vmware_username %s --vmware_passwd %s --vmware_vmpg_vswitch %s" % (vmware_info['esxi']['ip'], vmware_info['esxi']['username'], \
                                vmware_info['esxi']['password'], vmware_info['vswitch'])
                internal_vip = get_contrail_internal_vip()
                if internal_vip:
                    cmd += " --internal_vip %s" % internal_vip
                    cmd += " --mgmt_self_ip %s" % compute_mgmt_ip
                external_vip = get_from_testbed_dict('ha', 'external_vip', None)
                if external_vip:
                    cmd += ' --external_vip %s' % external_vip
                if manage_nova_compute == 'no':
                    cmd = cmd + "  --no_contrail_openstack"
                print cmd
                run(cmd)
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
            tgt_hostname = run("hostname")

        with cd(UTILS_DIR):
            #Configure global system config with the same ASN
            run("python provision_control.py --api_server_ip %s --api_server_port 8082 --router_asn %s %s" \
                        %(cfgm_ip, testbed.router_asn, get_mt_opts()))
            run("python provision_control.py --api_server_ip %s --api_server_port 8082 --host_name %s --host_ip %s --router_asn %s --oper add %s" \
                        %(cfgm_ip, tgt_hostname, tgt_ip, testbed.router_asn, get_mt_opts()))
#end prov_control_bgp

@roles('cfgm')
@task
def prov_external_bgp():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    pre_cmd = ''

    for ext_bgp in testbed.ext_routers:
        ext_bgp_name = ext_bgp[0]
        ext_bgp_ip   = ext_bgp[1]
        with cd(UTILS_DIR):
            run("%s python provision_mx.py --api_server_ip %s --api_server_port 8082 --router_name %s --router_ip %s --router_asn %s %s" \
                        %(pre_cmd, cfgm_ip, ext_bgp_name, ext_bgp_ip, testbed.router_asn, get_mt_opts()))
#end prov_control_bgp

@roles('cfgm')
@task
def prov_metadata_services():
    cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    openstack_host = get_control_host_string(env.roledefs['openstack'][0])
    openstack_ip = get_openstack_internal_vip() or hstr_to_ip(openstack_host)
    ks_admin_user, ks_admin_password = get_openstack_credentials()
    metadata_args = "--admin_user %s\
         --admin_password %s --linklocal_service_name metadata\
         --linklocal_service_ip 169.254.169.254\
         --linklocal_service_port 80\
         --ipfabric_service_ip %s\
         --ipfabric_service_port 8775\
         --oper add --api_server_ip %s" %(ks_admin_user, ks_admin_password, openstack_ip, cfgm_ip)
    run("python /opt/contrail/utils/provision_linklocal.py %s" %(metadata_args))
#end prov_metadata_services

@roles('cfgm')
@task
def prov_encap_type():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))
    ks_admin_user, ks_admin_password = get_openstack_credentials()
    if 'encap_priority' not in env.keys(): env.encap_priority="MPLSoUDP,MPLSoGRE,VXLAN"
    encap_args = "--admin_user %s\
     --admin_password %s\
     --encap_priority %s \
     --oper add" %(ks_admin_user, ks_admin_password, env.encap_priority)
    run("python /opt/contrail/utils/provision_encap.py %s" %(encap_args))
    sleep(10)
#end prov_encap_type

@roles('build')
@task
def setup_all(reboot='True'):
    """Provisions required contrail services in all nodes as per the role definition.
    """
    execute('setup_ha')
    execute('setup_rabbitmq_cluster')
    execute('increase_limits')
    execute('increase_ulimits')
    execute('setup_database')
    execute('verify_database')
    execute('setup_openstack')
    if get_openstack_internal_vip():
        execute('sync_keystone_ssl_certs')
        execute('setup_cluster_monitors')
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
    if reboot == 'True':
        print "Rebooting the compute nodes after setup all."
        execute('compute_reboot')
        #Clear the connections cache
        connections.clear()
        execute('verify_compute')
#end setup_all

@roles('build')
@task
def setup_without_openstack(manage_nova_compute='yes'):
    """Provisions required contrail packages in all nodes as per the role definition except the openstack.
       User has to provision the openstack node with their custom openstack pakckages.
       If manage_nova_compute = no; Only vrouter services is provisioned, nova-compute will be skipped in the compute node.
    """
    execute(setup_rabbitmq_cluster)
    execute(increase_limits)
    execute(setup_database)
    execute(setup_cfgm)
    execute(setup_control)
    execute(setup_collector)
    execute(setup_webui)
    execute('setup_vrouter', manage_nova_compute)
    execute(prov_control_bgp)
    execute(prov_external_bgp)
    execute(prov_metadata_services)
    execute(prov_encap_type)
    print "Rebooting the compute nodes after setup all."
    execute(compute_reboot)

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
    execute(bash_autocomplete_systemd)
    execute(setup_rabbitmq_cluster)
    execute(increase_limits)
    execute(increase_ulimits)
    execute(setup_database)
    execute(setup_openstack)
    execute(setup_cfgm)
    execute(setup_control)
    execute(setup_collector)
    execute(setup_webui)
    execute(setup_vrouter)
    execute(prov_control_bgp)
    execute(prov_external_bgp)
    execute(prov_metadata_services)
    execute(prov_encap_type)
    execute(add_images)
    print "Rebooting the compute nodes after setup all."
    execute(compute_reboot)

@roles('build')
@task
def run_setup_demo():
    execute(bash_autocomplete_systemd)
    execute(setup_rabbitmq_cluster)
    execute(increase_limits)
    execute(increase_ulimits)
    execute(setup_database)
    execute(setup_openstack)
    execute(setup_cfgm)
    execute(setup_control)
    execute(setup_collector)
    execute(setup_webui)
    execute(setup_vrouter)
    execute(prov_control_bgp)
    execute(prov_external_bgp)
    execute(prov_metadata_services)
    execute(prov_encap_type)
    execute(config_demo)
    execute(add_images)
    execute(compute_reboot)
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

    for host in hosts.keys():
        cmd = 'python setup-vnc-interfaces.py'
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
            with settings(host_string=host):
                with cd(INSTALLER_DIR):
                    run(cmd)
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
        execute(setup_openstack)
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
    execute(setup_vrouter)
    execute(compute_reboot)
#end reset_config

@roles('build')
@task
def prov_vmware_compute_vm():
    compute_vm_info = getattr(testbed, 'compute_vm', None) 
    if not compute_vm_info:
        return
    for compute_node in env.roledefs['compute']:
        if compute_node in compute_vm_info.keys():
            configure_esxi_network(compute_vm_info[compute_node])
            create_ovf(compute_vm_info[compute_node])
#end prov_compute_vm

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
        cmd = 'python setup-vnc-static-routes.py' +\
                      dest + gw + netmask + intf
        if vlan:
            cmd += ' --vlan %s'%vlan
        with settings(host_string=tgt_host):
            with cd(INSTALLER_DIR):
                run(cmd)
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

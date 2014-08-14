import tempfile

from fabfile.config import *
from fabfile.templates import openstack_haproxy, collector_haproxy
from fabfile.tasks.helpers import enable_haproxy
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import get_keystone_ip, get_control_host_string,\
                               hstr_to_ip, get_from_testbed_dict

@task
@EXECUTE_TASK
@roles('openstack')
def fix_restart_xinetd_conf():
    """Fix contrail-mysqlprobe to accept connection only from this node"""
    execute('fix_restart_xinetd_conf_node', env.host_string)

@task
def fix_restart_xinetd_conf_node(*args):
    """Fix contrail-mysqlprobe to accept connection only from this node, USAGE:fab fix_restart_xinetd_conf_node:user@1.1.1.1,user@2.2.2.2"""
    for host_string in args:
        self_ip = hstr_to_ip(get_control_host_string(host_string))
        run("sed -i -e 's#only_from       = 0.0.0.0/0#only_from       = %s 127.0.0.1#' /etc/xinetd.d/contrail-mysqlprobe" % self_ip)
        run("service xinetd restart")
        run("chkconfig xinetd on")

@task
@EXECUTE_TASK
@roles('openstack')
def fix_memcache_conf():
    """Increases the memcached memory to 2048 and listen address to mgmt ip"""
    execute('fix_memcache_conf_node', env.host_string)

@task
def fix_memcache_conf_node(*args):
    """Increases the memcached memory to 2048 and listen address to mgmt ip. USAGE:fab fix_memcache_conf_node:user@1.1.1.1,user@2.2.2.2"""
    memory = '2048'
    for host_string in args:
        listen_ip = hstr_to_ip(env.host_string)
        with settings(host_string=host_string, warn_only=True):
            if detect_ostype() == 'Ubuntu':
                memcache_conf='/etc/memcached.conf'
                if run('grep "\-m " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    run('echo "-m %s" >> %s' % (memory, memcache_conf))
                else:
                    run("sed -i -e 's/\-m.*/\-m %s/' %s" % (memory, memcache_conf))
                if run('grep "\-l " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    run('echo "-l %s" >> %s' % (listen_ip, memcache_conf))
                else:
                    run("sed -i -e 's/\-l.*/\-l %s/' %s" % (listen_ip, memcache_conf))
            else:
                memcache_conf='/etc/sysconfig/memcached'
                # Need to implement when HA supported in centos.

@task
@EXECUTE_TASK
@roles('cfgm')
def tune_tcp():
    with settings(hide('stderr'), warn_only=True):
        if run("grep '^net.netfilter.nf_conntrack_max' /etc/sysctl.conf").failed:
            run('echo "net.netfilter.nf_conntrack_max = 256000" >> /etc/sysctl.conf')
        if run("grep '^net.netfilter.nf_conntrack_tcp_timeout_time_wait' /etc/sysctl.conf").failed:
            run('echo "net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30" >> /etc/sysctl.conf')
        if run("grep '^net.ipv4.tcp_syncookies' /etc/sysctl.conf").failed:
            run('echo "net.ipv4.tcp_syncookies = 1" >> /etc/sysctl.conf')
        if run("grep '^net.ipv4.tcp_tw_recycle' /etc/sysctl.conf").failed:
            run('echo "net.ipv4.tcp_tw_recycle = 1" >> /etc/sysctl.conf')
        if run("grep '^net.ipv4.tcp_tw_reuse' /etc/sysctl.conf").failed:
            run('echo "net.ipv4.tcp_tw_reuse = 1" >> /etc/sysctl.conf')
        if run("grep '^net.ipv4.tcp_fin_timeout' /etc/sysctl.conf").failed:
            run('echo "net.ipv4.tcp_fin_timeout = 30" >> /etc/sysctl.conf')

@task
@EXECUTE_TASK
@roles('openstack')
def mount_glance_images():
    nfs_server = get_from_testbed_dict('ha', 'nfs_server', hstr_to_ip(env.roledefs['compute'][0]))
    nfs_glance_path = get_from_testbed_dict('ha', 'nfs_glance_path', '/var/tmp/glance-images/')
    with settings(warn_only=True):
        out = run('sudo mount %s:%s /var/lib/glance/images' % (nfs_server, nfs_glance_path))
        if out.failed and 'already mounted' not in out:
            raise RuntimeError(out)
        if run('grep "%s:%s /var/lib/glance/images nfs" /etc/fstab' % (nfs_server, nfs_glance_path)).failed:
            run('echo "%s:%s /var/lib/glance/images nfs nfsvers=3,hard,intr,auto 0 0" >> /etc/fstab' % (nfs_server, nfs_glance_path))

@task
def setup_glance_images_loc():
    nfs_server = get_from_testbed_dict('ha', 'nfs_server', None)
    nfs_glance_path = get_from_testbed_dict('ha', 'nfs_glance_path', '/var/tmp/glance-images/')
    if not nfs_server:
        with settings(host_string=env.roledefs['compute'][0]):
            run('mkdir -p /var/tmp/glance-images/')
            run('chmod 777 /var/tmp/glance-images/')
            run('echo "/var/tmp/glance-images *(rw,sync,no_subtree_check)" >> /etc/exports')
            run('sudo /etc/init.d/nfs-kernel-server restart')
    execute('mount_glance_images')

@task
@serial
@hosts(*env.roledefs['openstack'][1:])
def sync_keystone_ssl_certs():
    host_string = env.host_string
    temp_dir= tempfile.mkdtemp()
    with settings(host_string=env.roledefs['openstack'][0], password=env.passwords[env.roledefs['openstack'][0]]):
       get('/etc/keystone/ssl/', temp_dir)
    with settings(host_string=host_string, password=env.passwords[host_string]):
        put('%s/ssl/' % temp_dir, '/etc/keystone/')
        run('service keystone restart')

@task
def fix_wsrep_cluster_address():
    openstack_host_list = [get_control_host_string(openstack_host) for openstack_host in env.roledefs['openstack']]
    galera_ip_list = [hstr_to_ip(galera_host) for galera_host in openstack_host_list]
    with settings(host_string=env.roledefs['openstack'][0], password=env.passwords[env.roledefs['openstack'][0]]):
        wsrep_conf = '/etc/mysql/my.cnf'
        if detect_ostype() in ['Ubuntu']:
            wsrep_conf = '/etc/mysql/conf.d/wsrep.cnf'
        run('sed -ibak "s#wsrep_cluster_address=.*#wsrep_cluster_address=gcomm://%s:4567#g" %s' %
              (':4567,'.join(galera_ip_list), wsrep_conf))


@task
@roles('build')
def bootstrap_galera_cluster():
    openstack_node = env.roledefs['openstack'][0]
    with settings(host_string=openstack_node, password=env.passwords[openstack_node]):
        run("service mysql start --wsrep_cluster_address=gcomm://")
    for openstack_node in env.roledefs['openstack'][1:]:
        with settings(host_string=openstack_node, password=env.passwords[openstack_node]):
            run("service mysql restart")


@task
@EXECUTE_TASK
@roles('openstack')
def setup_cluster_monitors():
    """Task to start manage the contrail cluster manitor."""
    run("service contrail-hamon restart")
    run("chkconfig contrail-hamon on")

@task
@serial
@roles('openstack')
def setup_galera_cluster():
    """Task to cluster the openstack nodes with galera"""
    if len(env.roledefs['openstack']) <= 1:
        print "Single Openstack cluster, skipping galera cluster setup."
        return

    if env.roledefs['openstack'].index(env.host_string) == 0:
        execute('setup_passwordless_ssh', *env.roledefs['openstack'])
    self_host = get_control_host_string(env.host_string)
    self_ip = hstr_to_ip(self_host)
    openstack_host_password = env.passwords[env.host_string]

    if (getattr(env, 'openstack_admin_password', None)):
        openstack_admin_password = env.openstack_admin_password
    else:
        openstack_admin_password = 'contrail123'

    openstack_host_list = [get_control_host_string(openstack_host)\
                           for openstack_host in env.roledefs['openstack']]
    galera_ip_list = [hstr_to_ip(galera_host)\
                      for galera_host in openstack_host_list]
    keystone_ip = get_keystone_ip()
    internal_vip = get_from_testbed_dict('ha', 'internal_vip', None)

    with cd(INSTALLER_DIR):
        run("PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-galera.py\
            --self_ip %s --keystone_ip %s --galera_ip_list %s\
            --internal_vip %s --openstack_index %d" % (openstack_host_password,
                openstack_admin_password, self_ip, keystone_ip,
                ' '.join(galera_ip_list), internal_vip,
                (openstack_host_list.index(self_host) + 1)))


@task
@EXECUTE_TASK
@roles('openstack')
def setup_keepalived():
    """Task to provision VIP for openstack nodes with keepalived"""
    mgmt_ip = hstr_to_ip(env.host_string)
    self_host = get_control_host_string(env.host_string)
    self_ip = hstr_to_ip(self_host)
    openstack_host_password = env.passwords[env.host_string]
    
    if (getattr(env, 'openstack_admin_password', None)):
        openstack_admin_password = env.openstack_admin_password
    else:
        openstack_admin_password = 'contrail123'
        
    internal_vip = get_from_testbed_dict('ha', 'internal_vip', None)
    external_vip = get_from_testbed_dict('ha', 'external_vip', None)
    openstack_host_list = [get_control_host_string(openstack_host)\
                           for openstack_host in env.roledefs['openstack']]
 
    with cd(INSTALLER_DIR):
        cmd = "PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-keepalived.py\
               --self_ip %s --internal_vip %s --mgmt_self_ip %s\
               --openstack_index %d --num_nodes %d" % (openstack_host_password,
               openstack_admin_password, self_ip, internal_vip, mgmt_ip,
               (openstack_host_list.index(self_host) + 1), len(env.roledefs['openstack']))
        if external_vip:
             cmd += ' --external_vip %s' % external_vip
        run(cmd)

@task
@EXECUTE_TASK
@roles('openstack')
def fixup_restart_haproxy_in_openstack():
    execute('fixup_restart_haproxy_in_openstack_node', env.host_string)

@task
def fixup_restart_haproxy_in_openstack_node(*args):
    keystone_server_lines = ''
    keystone_admin_server_lines = ''
    glance_server_lines = ''
    cinder_server_lines = ''
    nova_api_server_lines = ''
    nova_meta_server_lines = ''
    nova_vnc_server_lines = ''
    memcached_server_lines = ''
    rabbitmq_server_lines = ''
    mysql_server_lines = ''
    space = ' ' * 3 

    for host_string in env.roledefs['openstack']:
        server_index = env.roledefs['openstack'].index(host_string) + 1
        mgmt_host_ip = hstr_to_ip(host_string)
        host_ip = hstr_to_ip(get_control_host_string(host_string))
        keystone_server_lines +=\
            '%s server %s %s:6000 check port 3337 observe layer7 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        keystone_admin_server_lines +=\
            '%s server %s %s:35358 check port 3337 observe layer7 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        glance_server_lines +=\
            '%s server %s %s:9393 check port 3337 observe layer7 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        cinder_server_lines +=\
            '%s server %s %s:9776 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        nova_api_server_lines +=\
            '%s server %s %s:9774 check port 3337 observe layer7 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        nova_meta_server_lines +=\
            '%s server %s %s:9775 check port 3337 observe layer7 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        nova_vnc_server_lines  +=\
            '%s server %s %s:6999 check inter 2000 rise 2 fall 3\n'\
             % (space, mgmt_host_ip, mgmt_host_ip)
        if server_index <= 2:
            memcached_server_lines +=\
                '%s server repcache%s %s:11211 check inter 2000 rise 2 fall 3\n'\
                 % (space, server_index, host_ip)
        rabbitmq_server_lines +=\
            '%s server rabbit%s %s:5672 check inter 2000 rise 2 fall 3 weight 1 maxconn 500\n'\
             % (space, server_index, host_ip)
        mysql_server_lines +=\
            '%s server mysql%s %s:3306 weight 1\n'\
             % (space, server_index, host_ip)


    for host_string in env.roledefs['openstack']:
        haproxy_config = openstack_haproxy.template.safe_substitute({
            '__keystone_backend_servers__' : keystone_server_lines,
            '__keystone_admin_backend_servers__' : keystone_admin_server_lines,
            '__glance_backend_servers__' : glance_server_lines,
            '__cinder_backend_servers__' : cinder_server_lines,
            '__nova_api_backend_servers__' : nova_api_server_lines,
            '__nova_meta_backend_servers__' : nova_meta_server_lines,
            '__nova_vnc_backend_servers__' : nova_vnc_server_lines,
            '__memcached_servers__' : memcached_server_lines,
            '__rabbitmq_servers__' : rabbitmq_server_lines,
            '__mysql_servers__' : mysql_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            })

    for host_string in args:
        with settings(host_string=host_string):
            # chop old settings including pesky default from pkg...
            tmp_fname = "/tmp/haproxy-%s-config" % (host_string)
            get("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-openstack-marker-start/,/^#contrail-openstack-marker-end/d' %s" % (tmp_fname))
                local("sed -i -e 's/*:5000/*:5001/' %s" % (tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (tmp_fname))
                local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (tmp_fname))
                local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (tmp_fname))
                local('sed -i "/^global/a\\        tune.bufsize 16384" %s' % tmp_fname)
                local('sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % tmp_fname)
                local('sed -i "/^global/a\        spread-checks 4" %s' % tmp_fname)
            # ...generate new ones
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(haproxy_config)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg")
            local("rm %s" %(tmp_fname))

        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            run("chkconfig haproxy on")
            run("service supervisor-openstack stop")
            enable_haproxy()
            run("service haproxy restart")
            #Change the keystone admin/public port
            run("openstack-config --set /etc/keystone/keystone.conf DEFAULT public_port 6000")
            run("openstack-config --set /etc/keystone/keystone.conf DEFAULT admin_port 35358")


@task
@EXECUTE_TASK
@roles('openstack')
def fixup_restart_haproxy_in_collector():
    execute('fixup_restart_haproxy_in_collector_node', env.host_string)

@task
def fixup_restart_haproxy_in_collector_node(*args):
    contrail_analytics_api_server_lines = ''
    space = ' ' * 3

    for host_string in env.roledefs['collector']:
        server_index = env.roledefs['collector'].index(host_string) + 1
        mgmt_host_ip = hstr_to_ip(host_string)
        host_ip = hstr_to_ip(get_control_host_string(host_string))
        contrail_analytics_api_server_lines +=\
            '%s server %s %s:9081 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)

    for host_string in env.roledefs['collector']:
        haproxy_config = collector_haproxy.template.safe_substitute({
            '__contrail_analytics_api_backend_servers__' : contrail_analytics_api_server_lines,
            '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            })

    for host_string in args:
        with settings(host_string=host_string):
            # chop old settings including pesky default from pkg...
            tmp_fname = "/tmp/haproxy-%s-config" % (host_string)
            get("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-collector-marker-start/,/^#contrail-collector-marker-end/d' %s" % (tmp_fname))
                local("sed -i -e 's/*:5000/*:5001/' %s" % (tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (tmp_fname))
                local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (tmp_fname))
                local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (tmp_fname))
            # ...generate new ones
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(haproxy_config)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg")
            local("rm %s" %(tmp_fname))

        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            run("chkconfig haproxy on")
            enable_haproxy()
            run("service haproxy restart")

@task
@roles('build')
def setup_ha():
    execute('pre_check')
    if get_from_testbed_dict('ha', 'internal_vip', None):
        print "Multi Openstack setup, provisioning openstack HA."
        execute('setup_keepalived')
        execute('setup_galera_cluster')
        execute('fix_wsrep_cluster_address')
        execute('fix_restart_xinetd_conf')
        execute('fixup_restart_haproxy_in_openstack')
        execute('fixup_restart_haproxy_in_collector')
        execute('setup_glance_images_loc')
        execute('fix_memcache_conf')
        execute('tune_tcp')



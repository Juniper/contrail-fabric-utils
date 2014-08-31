import tempfile

from fabfile.config import *
from fabfile.templates import openstack_haproxy, collector_haproxy
from fabfile.tasks.helpers import enable_haproxy
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import get_keystone_ip, get_control_host_string,\
                               hstr_to_ip, get_from_testbed_dict, get_service_token,\
                               get_openstack_internal_vip, get_openstack_external_vip,\
                               get_contrail_internal_vip, get_contrail_external_vip

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
    internal_vip = get_openstack_internal_vip()

    with cd(INSTALLER_DIR):
        run("PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-galera.py\
            --self_ip %s --keystone_ip %s --galera_ip_list %s\
            --internal_vip %s --openstack_index %d" % (openstack_host_password,
                openstack_admin_password, self_ip, keystone_ip,
                ' '.join(galera_ip_list), internal_vip,
                (openstack_host_list.index(self_host) + 1)))

@task
def setup_keepalived():
    """Task to provision VIP for openstack/cfgm nodes with keepalived"""
    if get_openstack_internal_vip():
        execute('setup_openstack_keepalived')
    if get_contrail_internal_vip() != get_openstack_internal_vip():
        execute('setup_contrail_keepalived')

@task
@serial
@roles('openstack')
def setup_openstack_keepalived():
    """Task to provision VIP for openstack nodes with keepalived"""
    enable_haproxy()
    run("service haproxy restart")
    setup_keepalived_node('openstack')

@task
@serial
@roles('cfgm')
def setup_contrail_keepalived():
    """Task to provision VIP for cfgm nodes with keepalived"""
    enable_haproxy()
    run("service haproxy restart")
    setup_keepalived_node('cfgm')

def setup_keepalived_node(role):
    """Task to provision VIP for node with keepalived"""
    mgmt_ip = hstr_to_ip(env.host_string)
    self_host = get_control_host_string(env.host_string)
    self_ip = hstr_to_ip(self_host)
    openstack_host_password = env.passwords[env.host_string]
    
    if (getattr(env, 'openstack_admin_password', None)):
        openstack_admin_password = env.openstack_admin_password
    else:
        openstack_admin_password = 'contrail123'
        
    internal_vip = get_openstack_internal_vip()
    external_vip = get_openstack_external_vip()
    if role == 'cfgm':
        internal_vip = get_contrail_internal_vip()
        external_vip = get_contrail_external_vip()
    keepalived_host_list = [get_control_host_string(keepalived_host)\
                           for keepalived_host in env.roledefs[role]]
    myindex = keepalived_host_list.index(self_host)
    if myindex >= 1:
        # Wait for VIP to be assiciated to MASTER
        with settings(host_string=env.roledefs[role][0], warn_only=True):
            while run("ip addr | grep %s" % internal_vip).failed:
                sleep(2)
                print "Waiting for VIP to be associated to MASTER VRRP."
                continue
 
    with cd(INSTALLER_DIR):
        cmd = "PASSWORD=%s ADMIN_TOKEN=%s python setup-vnc-keepalived.py\
               --self_ip %s --internal_vip %s --mgmt_self_ip %s\
               --self_index %d --num_nodes %d --role %s" % (openstack_host_password,
               openstack_admin_password, self_ip, internal_vip, mgmt_ip,
               (keepalived_host_list.index(self_host) + 1), len(env.roledefs[role]),
               role)
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
            '%s server %s %s:6000 check inter 2000 rise 2 fall 1 check port 3337 observe layer7 check port 3306 observe layer4\n'\
             % (space, host_ip, host_ip)
        keystone_admin_server_lines +=\
            '%s server %s %s:35358 check inter 2000 rise 2 fall 1 check port 3337 observe layer7 check port 3306 observe layer4\n'\
             % (space, host_ip, host_ip)
        glance_server_lines +=\
            '%s server %s %s:9393 check inter 2000 rise 2 fall 1 check port 3337 observe layer7 check port 3306 observe layer4\n'\
             % (space, host_ip, host_ip)
        cinder_server_lines +=\
            '%s server %s %s:9776 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        nova_api_server_lines +=\
            '%s server %s %s:9774 check inter 2000 rise 2 fall 1 check port 3337 observe layer7 check port 3306 observe layer4\n'\
             % (space, host_ip, host_ip)
        nova_meta_server_lines +=\
            '%s server %s %s:9775 check inter 2000 rise 2 fall 1 check port 3337 observe layer7 check port 3306 observe layer4\n'\
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
                # Remove default HA config
                local("sed -i '/listen\sappli1-rewrite/,/rspidel/d' %s" % tmp_fname)
                local("sed -i '/listen\sappli3-relais/,/rspidel/d' %s" % tmp_fname)
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
@roles('cfgm')
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
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (tmp_fname))
                local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (tmp_fname))
                local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (tmp_fname))
                # Remove default HA config
                local("sed -i '/listen\sappli1-rewrite/,/rspidel/d' %s" % tmp_fname)
                local("sed -i '/listen\sappli3-relais/,/rspidel/d' %s" % tmp_fname)
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
@serial
@roles('openstack')
def fix_cmon_param_and_add_keys_to_compute():
    cmon_param = '/etc/contrail/ha/cmon_param'
    compute_host_list = []
    for host_string in env.roledefs['compute']:
        with settings(host_string=host_string, password=env.passwords[host_string]):
            host_name = run('hostname')
        compute_host_list.append(host_name)
    computes = 'COMPUTES=("' + '" "'.join(compute_host_list) + '")'
    run("echo '%s' >> %s" % (computes, cmon_param))
    run("echo 'COMPUTES_SIZE=${#COMPUTES[@]}' >> %s" % cmon_param)
    run("echo 'COMPUTES_USER=root' >> %s" % cmon_param)
    run("echo 'PERIODIC_RMQ_CHK_INTER=60' >> %s" % cmon_param)
    id_rsa_pubs = {}
    if files.exists('/root/.ssh'):
        run('chmod 700 /root/.ssh')
    if not files.exists('/root/.ssh/id_rsa') and not files.exists('/root/.ssh/id_rsa.pub'):
        run('ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N ""')
    elif not files.exists('/root/.ssh/id_rsa') or not files.exists('/root/.ssh/id_rsa.pub'):
        run('rm -rf /root/.ssh/id_rsa*')
        run('ssh-keygen -b 2048 -t rsa -f /root/.ssh/id_rsa -q -N ""')
    id_rsa_pubs.update({env.host_string : run('cat /root/.ssh/id_rsa.pub')})
    for host_string in env.roledefs['compute']:
        with settings(host_string=host_string):
            run("mkdir -p /root/.ssh/")
            for host, id_rsa_pub in id_rsa_pubs.items():
                files.append('/root/.ssh/authorized_keys', id_rsa_pub)
            run('chmod 640 /root/.ssh/authorized_keys')

@task
@roles('build')
def create_and_copy_service_token():
    service_token = get_service_token() or run("openssl rand -hex 10")
    for host_string in env.roledefs['openstack']:
        with settings(host_string=host_string):
            if (files.exists('/etc/contrail/service.token') and env.roledefs['openstack'].index(host_string) == 0):
                service_token = run("cat /etc/contrail/service.token")
            else:
                run("echo '%s' > /etc/contrail/service.token" % service_token)

@task
@hosts(*env.roledefs['openstack'][:1])
def setup_cmon_schema():
    """Task to configure cmon schema in the openstack nodes to monitor galera cluster"""
    if len(env.roledefs['openstack']) <= 1:
        print "Single Openstack cluster, skipping cmon schema  setup."
        return

    openstack_host_list = [get_control_host_string(openstack_host)\
                           for openstack_host in env.roledefs['openstack']]
    galera_ip_list = [hstr_to_ip(galera_host)\
                      for galera_host in openstack_host_list]
    internal_vip = get_openstack_internal_vip()

    mysql_token = run("cat /etc/contrail/mysql.token")
    pdist = detect_ostype()
    if pdist in ['Ubuntu']:
        mysql_svc = 'mysql'
    elif pdist in ['centos', 'redhat']:
        mysql_svc = 'mysqld'
    # Create cmon schema
    run('mysql -u root -p%s -e "CREATE SCHEMA IF NOT EXISTS cmon"' % mysql_token)
    run('mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_db.sql' % mysql_token)
    run('mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_data.sql' % mysql_token)

    # insert static data
    run('mysql -u root -p%s -e "use cmon; insert into cluster(type) VALUES (\'galera\')"' % mysql_token)

    host_list = galera_ip_list + ['localhost', '127.0.0.1', internal_vip]
    # Create cmon user
    for host in host_list:
        mysql_cmon_user_cmd = 'mysql -u root -p%s -e "CREATE USER \'cmon\'@\'%s\' IDENTIFIED BY \'cmon\'"' % (
                               mysql_token, host)
        with settings(hide('everything'),warn_only=True):
            run(mysql_cmon_user_cmd)

    mysql_cmd =  "mysql -uroot -p%s -e" % mysql_token
    # Grant privilages for cmon user.
    for host in host_list:
        run('%s "GRANT ALL PRIVILEGES on *.* TO cmon@%s IDENTIFIED BY \'cmon\' WITH GRANT OPTION"' %
               (mysql_cmd, host))
    # Restarting mysql in all openstack nodes
    for host_string in env.roledefs['openstack']:
        with settings(host_string=host_string):
            run("service %s restart" % mysql_svc)


@task
@roles('build')
def setup_ha():
    execute('pre_check')
    if get_openstack_internal_vip():
        print "Multi Openstack setup, provisioning openstack HA."
        execute('setup_keepalived')
        execute('setup_galera_cluster')
        execute('fix_wsrep_cluster_address')
        execute('setup_cmon_schema')
        execute('fix_restart_xinetd_conf')
        execute('fixup_restart_haproxy_in_openstack')
        execute('fixup_restart_haproxy_in_collector')
        execute('setup_glance_images_loc')
        execute('fix_memcache_conf')
        execute('tune_tcp')
        execute('fix_cmon_param_and_add_keys_to_compute')
        execute('create_and_copy_service_token')



import tempfile

from fabfile.config import *
from fabfile.templates import openstack_haproxy, collector_haproxy
from fabfile.tasks.helpers import enable_haproxy
from fabfile.utils.fabos import detect_ostype, get_as_sudo
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
        sudo("sed -i -e 's#only_from       = 0.0.0.0/0#only_from       = %s 127.0.0.1#' /etc/xinetd.d/contrail-mysqlprobe" % self_ip)
        sudo("service xinetd restart")
        sudo("chkconfig xinetd on")

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
            if detect_ostype() == 'ubuntu':
                memcache_conf='/etc/memcached.conf'
                if sudo('grep "\-m " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    sudo('echo "-m %s" >> %s' % (memory, memcache_conf))
                else:
                    sudo("sed -i -e 's/\-m.*/\-m %s/' %s" % (memory, memcache_conf))
                if sudo('grep "\-l " %s' % memcache_conf).failed:
                    #Write option to memcached config file
                    sudo('echo "-l %s" >> %s' % (listen_ip, memcache_conf))
                else:
                    sudo("sed -i -e 's/\-l.*/\-l %s/' %s" % (listen_ip, memcache_conf))
            else:
                memcache_conf='/etc/sysconfig/memcached'
                # Need to implement when HA supported in centos.

@task
@EXECUTE_TASK
@roles('cfgm')
def tune_tcp():
    with settings(hide('stderr'), warn_only=True):
        if sudo("grep '^net.netfilter.nf_conntrack_max' /etc/sysctl.conf").failed:
            sudo('echo "net.netfilter.nf_conntrack_max = 256000" >> /etc/sysctl.conf')
        if sudo("grep '^net.netfilter.nf_conntrack_tcp_timeout_time_wait' /etc/sysctl.conf").failed:
            sudo('echo "net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30" >> /etc/sysctl.conf')
        if sudo("grep '^net.ipv4.tcp_syncookies' /etc/sysctl.conf").failed:
            sudo('echo "net.ipv4.tcp_syncookies = 1" >> /etc/sysctl.conf')
        if sudo("grep '^net.ipv4.tcp_tw_recycle' /etc/sysctl.conf").failed:
            sudo('echo "net.ipv4.tcp_tw_recycle = 1" >> /etc/sysctl.conf')
        if sudo("grep '^net.ipv4.tcp_tw_reuse' /etc/sysctl.conf").failed:
            sudo('echo "net.ipv4.tcp_tw_reuse = 1" >> /etc/sysctl.conf')
        if sudo("grep '^net.ipv4.tcp_fin_timeout' /etc/sysctl.conf").failed:
            sudo('echo "net.ipv4.tcp_fin_timeout = 30" >> /etc/sysctl.conf')
        if sudo("grep '^net.unix.max_dgram_qlen' /etc/sysctl.conf").failed:
            sudo('echo "net.unix.max_dgram_qlen = 1000" >> /etc/sysctl.conf')

@task
@EXECUTE_TASK
@roles('openstack')
def mount_glance_images():
    nfs_server = get_from_testbed_dict('ha', 'nfs_server', hstr_to_ip(env.roledefs['compute'][0]))
    nfs_glance_path = get_from_testbed_dict('ha', 'nfs_glance_path', '/var/tmp/glance-images/')
    with settings(warn_only=True):
        out = sudo('sudo mount %s:%s /var/lib/glance/images' % (nfs_server, nfs_glance_path))
        if out.failed and 'already mounted' not in out:
            raise RuntimeError(out)
        if sudo('grep "%s:%s /var/lib/glance/images nfs" /etc/fstab' % (nfs_server, nfs_glance_path)).failed:
            sudo('echo "%s:%s /var/lib/glance/images nfs nfsvers=3,hard,intr,auto 0 0" >> /etc/fstab' % (nfs_server, nfs_glance_path))

@task
def setup_glance_images_loc():
    nfs_server = get_from_testbed_dict('ha', 'nfs_server', None)
    nfs_glance_path = get_from_testbed_dict('ha', 'nfs_glance_path', '/var/tmp/glance-images/')
    if not nfs_server:
        with settings(host_string=env.roledefs['compute'][0]):
            sudo('mkdir -p /var/tmp/glance-images/')
            sudo('chmod 777 /var/tmp/glance-images/')
            sudo('echo "/var/tmp/glance-images *(rw,sync,no_subtree_check)" >> /etc/exports')
            sudo('sudo /etc/init.d/nfs-kernel-server restart')
    execute('mount_glance_images')

@task
@serial
@hosts(*env.roledefs['openstack'][1:])
def sync_keystone_ssl_certs():
    host_string = env.host_string
    temp_dir= tempfile.mkdtemp()
    with settings(host_string=env.roledefs['openstack'][0], password=env.passwords[env.roledefs['openstack'][0]]):
       get_as_sudo('/etc/keystone/ssl/', temp_dir)
    with settings(host_string=host_string, password=env.passwords[host_string]):
        put('%s/ssl/' % temp_dir, '/etc/keystone/', use_sudo=True)
        sudo('service keystone restart')

@task
def fix_wsrep_cluster_address():
    openstack_host_list = [get_control_host_string(openstack_host) for openstack_host in env.roledefs['openstack']]
    galera_ip_list = [hstr_to_ip(galera_host) for galera_host in openstack_host_list]
    with settings(host_string=env.roledefs['openstack'][0], password=env.passwords[env.roledefs['openstack'][0]]):
        wsrep_conf = '/etc/mysql/my.cnf'
        if detect_ostype() in ['ubuntu']:
            wsrep_conf = '/etc/mysql/conf.d/wsrep.cnf'
        sudo('sed -ibak "s#wsrep_cluster_address=.*#wsrep_cluster_address=gcomm://%s:4567#g" %s' %
              (':4567,'.join(galera_ip_list), wsrep_conf))


@task
@roles('build')
def bootstrap_galera_cluster():
    openstack_node = env.roledefs['openstack'][0]
    with settings(host_string=openstack_node, password=env.passwords[openstack_node]):
        sudo("service mysql start --wsrep_cluster_address=gcomm://")
    for openstack_node in env.roledefs['openstack'][1:]:
        with settings(host_string=openstack_node, password=env.passwords[openstack_node]):
            sudo("service mysql restart")


@task
@EXECUTE_TASK
@roles('openstack')
def setup_cluster_monitors():
    """Task to start manage the contrail cluster manitor."""
    sudo("service contrail-hamon restart")
    sudo("chkconfig contrail-hamon on")

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

    openstack_host_list = [get_control_host_string(openstack_host)\
                           for openstack_host in env.roledefs['openstack']]
    galera_ip_list = [hstr_to_ip(galera_host)\
                      for galera_host in openstack_host_list]
    keystone_ip = get_keystone_ip()
    internal_vip = get_openstack_internal_vip()

    with cd(INSTALLER_DIR):
        sudo("setup-vnc-galera\
            --self_ip %s --keystone_ip %s --galera_ip_list %s\
            --internal_vip %s --openstack_index %d" % ( self_ip, keystone_ip,
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
    sudo("service haproxy restart")
    setup_keepalived_node('openstack')

@task
@serial
@roles('cfgm')
def setup_contrail_keepalived():
    """Task to provision VIP for cfgm nodes with keepalived"""
    enable_haproxy()
    sudo("service haproxy restart")
    setup_keepalived_node('cfgm')

def setup_keepalived_node(role):
    """Task to provision VIP for node with keepalived"""
    mgmt_ip = hstr_to_ip(env.host_string)
    self_host = get_control_host_string(env.host_string)
    self_ip = hstr_to_ip(self_host)

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
            while sudo("ip addr | grep %s" % internal_vip).failed:
                sleep(2)
                print "Waiting for VIP to be associated to MASTER VRRP."
                continue
 
    with cd(INSTALLER_DIR):
        cmd = "setup-vnc-keepalived\
               --self_ip %s --internal_vip %s --mgmt_self_ip %s\
               --self_index %d --num_nodes %d --role %s" % ( self_ip,
                internal_vip, mgmt_ip, (keepalived_host_list.index(self_host) + 1),
                len(env.roledefs[role]), role)
        if external_vip:
             cmd += ' --external_vip %s' % external_vip
        sudo(cmd)

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
    heat_server_lines = ''
    cinder_server_lines = ''
    ceph_restapi_server_lines = ''
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
            '%s server %s %s:6000 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        keystone_admin_server_lines +=\
            '%s server %s %s:35358 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        glance_server_lines +=\
            '%s server %s %s:9393 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        heat_server_lines +=\
            '%s server %s %s:8005 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        cinder_server_lines +=\
            '%s server %s %s:9776 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        ceph_restapi_server_lines +=\
            '%s server %s %s:5006 check inter 2000 rise 2 fall 3\n'\
             % (space, host_ip, host_ip)
        nova_api_server_lines +=\
            '%s server %s %s:9774 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        nova_meta_server_lines +=\
            '%s server %s %s:9775 check inter 2000 rise 2 fall 1\n'\
             % (space, host_ip, host_ip)
        nova_vnc_server_lines  +=\
            '%s server %s %s:6999 check inter 2000 rise 2 fall 3\n'\
             % (space, mgmt_host_ip, mgmt_host_ip)
        if server_index <= 2:
            memcached_server_lines +=\
                '%s server repcache%s %s:11211 check inter 2000 rise 2 fall 3\n'\
                 % (space, server_index, host_ip)
        if server_index == 1:
            rabbitmq_server_lines +=\
                '%s server rabbit%s %s:5672 weight 200 check inter 2000 rise 2 fall 3\n'\
                 % (space, server_index, host_ip)
        else:
            rabbitmq_server_lines +=\
                '%s server rabbit%s %s:5672 weight 100 check inter 2000 rise 2 fall 3 backup\n'\
                 % (space, server_index, host_ip)
        if server_index == 1:
             mysql_server_lines +=\
                   '%s server mysql%s %s:3306 weight 200 check inter 2000 rise 2 fall 3\n'\
                   % (space, server_index, host_ip)
        else:
             mysql_server_lines +=\
                   '%s server mysql%s %s:3306 weight 100 check inter 2000 rise 2 fall 3 backup\n'\
                   % (space, server_index, host_ip)        


    for host_string in env.roledefs['openstack']:
        haproxy_config = openstack_haproxy.template.safe_substitute({
            '__keystone_backend_servers__' : keystone_server_lines,
            '__keystone_admin_backend_servers__' : keystone_admin_server_lines,
            '__glance_backend_servers__' : glance_server_lines,
            '__heat_backend_servers__' : heat_server_lines,
            '__cinder_backend_servers__' : cinder_server_lines,
            '__ceph_restapi_backend_servers__' : ceph_restapi_server_lines,
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
            get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-openstack-marker-start/,/^#contrail-openstack-marker-end/d' %s" % (tmp_fname))
                local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
                local("sed -i -e 's/*:5000/*:5001/' %s" % (tmp_fname))
                local("sed -i -e 's/ssl-relay 0.0.0.0:8443/ssl-relay 0.0.0.0:5002/' %s" % (tmp_fname))
                local("sed -i -e 's/option\shttplog/option                  tcplog/' %s" % (tmp_fname))
                local("sed -i -e 's/maxconn 4096/maxconn 100000/' %s" % (tmp_fname))
                local('sed -i "/^global/a\\        tune.bufsize 16384" %s' % tmp_fname)
                local('sed -i "/^global/a\\        tune.maxrewrite 1024" %s' % tmp_fname)
                local('sed -i "/^global/a\        spread-checks 4" %s' % tmp_fname)
                local('sed -i "/^global/a\        maxconn 10000" %s' % tmp_fname)
                # Remove default HA config
                local("sed -i '/listen\sappli1-rewrite/,/rspidel/d' %s" % tmp_fname)
                local("sed -i '/listen\sappli3-relais/,/rspidel/d' %s" % tmp_fname)
            # ...generate new ones
            cfg_file = open(tmp_fname, 'a')
            cfg_file.write(haproxy_config)
            cfg_file.close()
            put(tmp_fname, "/etc/haproxy/haproxy.cfg", use_sudo=True)
            local("rm %s" %(tmp_fname))

        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            sudo("chkconfig haproxy on")
            sudo("service supervisor-openstack stop")
            enable_haproxy()
            sudo("service haproxy restart")
            #Change the keystone admin/public port
            sudo("openstack-config --set /etc/keystone/keystone.conf DEFAULT public_port 6000")
            sudo("openstack-config --set /etc/keystone/keystone.conf DEFAULT admin_port 35358")


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
            get_as_sudo("/etc/haproxy/haproxy.cfg", tmp_fname)
            with settings(warn_only=True):
                local("sed -i -e '/^#contrail-collector-marker-start/,/^#contrail-collector-marker-end/d' %s" % (tmp_fname))
                local("sed -i -e 's/frontend\s*main\s*\*:5000/frontend  main *:5001/' %s" %(tmp_fname))
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
            put(tmp_fname, "/etc/haproxy/haproxy.cfg", use_sudo=True)
            local("rm %s" %(tmp_fname))

        # haproxy enable
        with settings(host_string=host_string, warn_only=True):
            sudo("chkconfig haproxy on")
            enable_haproxy()
            sudo("service haproxy restart")

@task
@serial
@roles('openstack')
def fix_cmon_param_and_add_keys_to_compute():
    cmon_param = '/etc/contrail/ha/cmon_param'
    compute_host_list = []
    for host_string in env.roledefs['compute']:
        with settings(host_string=host_string, password=env.passwords[host_string]):
            host_name = sudo('hostname')
        compute_host_list.append(host_name)

    # Get AMQP host list
    amqp_in_role = 'cfgm'
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        amqp_in_role = 'openstack'
    amqp_host_list = []
    for host_string in env.roledefs[amqp_in_role]:
        with settings(host_string=host_string, password=env.passwords[host_string]):
            host_name = sudo('hostname')
        amqp_host_list.append(host_name)

    computes = 'COMPUTES=("' + '" "'.join(compute_host_list) + '")'
    sudo("echo '%s' >> %s" % (computes, cmon_param))
    sudo("echo 'COMPUTES_SIZE=${#COMPUTES[@]}' >> %s" % cmon_param)
    sudo("echo 'COMPUTES_USER=root' >> %s" % cmon_param)
    sudo("echo 'PERIODIC_RMQ_CHK_INTER=60' >> %s" % cmon_param)
    sudo("echo 'RABBITMQ_RESET=True' >> %s" % cmon_param)
    amqps = 'DIPHOSTS=("' + '" "'.join(amqp_host_list) + '")'
    sudo("echo '%s' >> %s" % (amqps, cmon_param))
    sudo("echo 'DIPS_HOST_SIZE=${#DIPHOSTS[@]}' >> %s" % cmon_param)
    id_rsa_pubs = {}
    if files.exists('~/.ssh', use_sudo=True):
        sudo('chmod 700 ~/.ssh')
    if (not files.exists('~/.ssh/id_rsa', use_sudo=True) and
        not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
        sudo('ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')
    elif (not files.exists('~/.ssh/id_rsa', use_sudo=True) or
         not files.exists('~/.ssh/id_rsa.pub', use_sudo=True)):
        sudo('rm -rf ~/.ssh/id_rsa*')
        sudo('ssh-keygen -b 2048 -t rsa -f ~/.ssh/id_rsa -q -N ""')
    id_rsa_pubs.update({env.host_string : sudo('cat ~/.ssh/id_rsa.pub')})
    for host_string in env.roledefs['compute']:
        with settings(host_string=host_string):
            sudo("mkdir -p ~/.ssh/")
            for host, id_rsa_pub in id_rsa_pubs.items():
                files.append('~/.ssh/authorized_keys',
                             id_rsa_pub, use_sudo=True)
            sudo('chmod 640 ~/.ssh/authorized_keys')

@task
@roles('build')
def create_and_copy_service_token():
    service_token = get_service_token() or sudo("openssl rand -hex 10")
    for host_string in env.roledefs['openstack']:
        with settings(host_string=host_string):
            if (files.exists('/etc/contrail/service.token', use_sudo=True) and
                env.roledefs['openstack'].index(host_string) == 0):
                service_token = sudo("cat /etc/contrail/service.token")
            else:
                sudo("echo '%s' > /etc/contrail/service.token" % service_token)

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

    mysql_token = sudo("cat /etc/contrail/mysql.token")
    pdist = detect_ostype()
    if pdist in ['ubuntu']:
        mysql_svc = 'mysql'
    elif pdist in ['centos', 'redhat']:
        mysql_svc = 'mysqld'
    # Create cmon schema
    sudo('mysql -u root -p%s -e "CREATE SCHEMA IF NOT EXISTS cmon"' % mysql_token)
    sudo('mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_db.sql' % mysql_token)
    sudo('mysql -u root -p%s < /usr/local/cmon/share/cmon/cmon_data.sql' % mysql_token)

    # insert static data
    sudo('mysql -u root -p%s -e "use cmon; insert into cluster(type) VALUES (\'galera\')"' % mysql_token)

    host_list = galera_ip_list + ['localhost', '127.0.0.1', internal_vip]
    # Create cmon user
    for host in host_list:
        mysql_cmon_user_cmd = 'mysql -u root -p%s -e "CREATE USER \'cmon\'@\'%s\' IDENTIFIED BY \'cmon\'"' % (
                               mysql_token, host)
        with settings(hide('everything'),warn_only=True):
            sudo(mysql_cmon_user_cmd)

    mysql_cmd =  "mysql -uroot -p%s -e" % mysql_token
    # Grant privilages for cmon user.
    for host in host_list:
        sudo('%s "GRANT ALL PRIVILEGES on *.* TO cmon@%s IDENTIFIED BY \'cmon\' WITH GRANT OPTION"' %
               (mysql_cmd, host))
    # Restarting mysql in all openstack nodes
    for host_string in env.roledefs['openstack']:
        with settings(host_string=host_string):
            sudo("service %s restart" % mysql_svc)


@task
@roles('build')
def setup_ha():
    execute('pre_check')

    if get_contrail_internal_vip():
        print "Contrail HA setup, provisioning contrail HA."
        execute('setup_keepalived')
        execute('fixup_restart_haproxy_in_collector')

    if get_openstack_internal_vip():
        print "Multi Openstack setup, provisioning openstack HA."
        execute('setup_galera_cluster')
        execute('fix_wsrep_cluster_address')
        execute('setup_cmon_schema')
        execute('fix_restart_xinetd_conf')
        execute('fixup_restart_haproxy_in_openstack')
        execute('setup_glance_images_loc')
        execute('fix_memcache_conf')
        execute('tune_tcp')
        execute('fix_cmon_param_and_add_keys_to_compute')
        execute('create_and_copy_service_token')

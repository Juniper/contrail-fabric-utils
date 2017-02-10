import uuid
import re
import time

from fabfile.config import *
from fabfile.templates import rabbitmq_config, rabbitmq_config_single_node,\
    rabbitmq_env_conf
from fabfile.utils.fabos import detect_ostype, get_openstack_services, is_xenial_or_above
from fabfile.tasks.helpers import disable_iptables, ping_test
from fabfile.utils.host import get_from_testbed_dict, get_control_host_string,\
    hstr_to_ip, get_openstack_internal_vip, get_contrail_internal_vip,\
    get_env_passwords

global ctrl
ctrl = "-ctrl"

def verfiy_and_update_hosts(host_name, host_string):
    # Need to have the alias created to map to the hostname
    # this is required for erlang node to cluster using
    # the same interface that is used for rabbitMQ TCP listener
    with settings(hide('stderr'), warn_only=True):
        if sudo('grep %s /etc/hosts' % (host_name+ctrl)).failed:
            sudo("echo '%s     %s     %s' >> /etc/hosts" % (hstr_to_ip(get_control_host_string(host_string)), host_name, host_name+ctrl))

@task
@EXECUTE_TASK
@roles('rabbit')
def set_tcp_keepalive():
    with settings(hide('stderr'), warn_only=True):
        if sudo("grep '^net.ipv4.tcp_keepalive_time' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_time = 5' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_time\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_probes\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_intvl\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")


@task
@EXECUTE_TASK
@roles('compute')
def set_tcp_keepalive_on_compute():
    with settings(hide('stderr'), warn_only=True):
        if sudo("grep '^net.ipv4.tcp_keepalive_time' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_time = 10' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_time\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_probes\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_intvl\s*=\s*[0-9]*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")

@task
@EXECUTE_TASK
@roles('rabbit')
def listen_at_supervisor_support_port():
    execute('listen_at_supervisor_support_port_node', env.host_string)

@task
def listen_at_supervisor_support_port_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if sudo("service supervisor-support-service status | grep running").failed:
                sudo("service supervisor-support-service start")
                if files.exists("/tmp/supervisord_support_service.sock"):
                    sudo("supervisorctl -s unix:///tmp/supervisord_support_service.sock stop all")
                else:
                    sudo("supervisorctl -s unix:///var/run/supervisord_support_service.sock stop all")


@task
@EXECUTE_TASK
@roles('rabbit')
def remove_mnesia_database():
   execute('remove_mnesia_database_node', env.host_string)

@task
def remove_mnesia_database_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo("service rabbitmq-server stop")
            if 'Killed' not in sudo("epmd -kill"):
                sudo("pkill -9  beam")
                sudo("pkill -9 epmd")
            if 'beam' in sudo("netstat -anp | grep beam"):
                sudo("pkill -9  beam")
                sudo("rm -rf /var/lib/rabbitmq/mnesia")

@task
@parallel
@roles('rabbit')
def set_guest_user_permissions():
    with settings(warn_only=True):
        sudo('rabbitmqctl set_permissions guest ".*" ".*" ".*"')

@task
@serial
@roles('rabbit')
def rabbitmq_env():
    erl_node_name = None
    rabbit_env_conf = '/etc/rabbitmq/rabbitmq-env.conf'
    with settings(host_string=env.host_string, password=get_env_passwords(env.host_string)):
        host_name = sudo('hostname -s') + ctrl
        erl_node_name = "rabbit@%s" % (host_name)
    rabbitmq_env_template = rabbitmq_env_conf
    rmq_env_conf = rabbitmq_env_template.template.safe_substitute({
            '__erl_node_ip__' : hstr_to_ip(get_control_host_string(env.host_string)),
            '__erl_node_name__' : erl_node_name,
            })
    tmp_fname = "/tmp/rabbitmq-env-%s.conf" % env.host_string
    cfg_file = open(tmp_fname, 'w')
    cfg_file.write(rmq_env_conf)
    cfg_file.close()
    put(tmp_fname, rabbit_env_conf, use_sudo=True)
    local("rm %s" %(tmp_fname))

@task
@serial
@roles('rabbit')
def config_rabbitmq():
    rabbit_hosts = []
    rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
    if len(env.roledefs['rabbit']) <= 1 and detect_ostype() == 'redhat':
        print "CONFIG_RABBITMQ: Skip creating rabbitmq.config for Single node setup"
        return
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string, password=get_env_passwords(host_string)):
            host_name = sudo('hostname -s') + ctrl
        rabbit_hosts.append("\'rabbit@%s\'" % host_name)
    rabbit_hosts = ', '.join(rabbit_hosts)
    rabbitmq_config_template = rabbitmq_config
    if len(env.roledefs['rabbit']) == 1:
        rabbitmq_config_template = rabbitmq_config_single_node
    rabbitmq_configs = rabbitmq_config_template.template.safe_substitute({
           '__control_intf_ip__' : hstr_to_ip(get_control_host_string(env.host_string)),
           '__rabbit_hosts__' : rabbit_hosts,
           })
    tmp_fname = "/tmp/rabbitmq_%s.config" % env.host_string
    cfg_file = open(tmp_fname, 'w')
    cfg_file.write(rabbitmq_configs)
    cfg_file.close()
    put(tmp_fname, "/etc/rabbitmq/rabbitmq.config", use_sudo=True)
    local("rm %s" %(tmp_fname))

@task
@parallel
@roles('rabbit')
def allow_rabbitmq_port():
    execute('allow_rabbitmq_port_node', env.host_string)

@task
def allow_rabbitmq_port_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            execute('disable_iptables')

@task
@parallel
@roles('rabbit')
def stop_rabbitmq_and_set_cookie(uuid):
    execute('stop_rabbitmq_and_set_cookie_node', uuid, env.host_string)

@task
def stop_rabbitmq_and_set_cookie_node(uuid, *args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            sudo("service rabbitmq-server stop")
            if 'Killed' not in sudo("epmd -kill"):
                sudo("pkill -9  beam")
                sudo("pkill -9 epmd")
            if 'beam' in sudo("netstat -anp | grep beam"):
                sudo("pkill -9  beam")
            sudo("rm -rf /var/lib/rabbitmq/mnesia/")
            sudo("echo '%s' > /var/lib/rabbitmq/.erlang.cookie" % uuid)
            sudo("chmod 400 /var/lib/rabbitmq/.erlang.cookie")
            sudo("chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie")

@task
@serial
@roles('rabbit')
def start_rabbitmq():
   execute('start_rabbitmq_node', env.host_string)

@task
def start_rabbitmq_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            openstack_services = get_openstack_services()
            if openstack_services['initsystem'] == 'systemd':
                sudo('systemctl daemon-reload')
                sudo('systemctl enable rabbitmq-server')
            sudo("service rabbitmq-server restart")

@task
@parallel
@roles('rabbit')
def rabbitmqctl_stop_app():
    sudo("rabbitmqctl stop_app")

@task
@parallel
@roles('rabbit')
def rabbitmqctl_reset():
    sudo("rabbitmqctl force_reset")

@task
@parallel
@hosts(*env.roledefs['rabbit'][1:])
def rabbitmqctl_start_app():
    execute("rabbitmqctl_start_app_node", env.host_string)

@task
def rabbitmqctl_start_app_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            sudo("rabbitmqctl start_app")

@task
@roles('rabbit')
def verify_rabbit_node_hostname():
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string):
            host_name = sudo('hostname -s')
        verfiy_and_update_hosts(host_name, host_string)

@task
@hosts(*env.roledefs['rabbit'][1:])
def add_node_to_rabbitmq_cluster():
    with settings(host_string=env.roledefs['rabbit'][0]):
        rabbit_node1 = sudo('hostname')
    this_rabbit_node = sudo('hostname')
    sudo("rabbitmqctl join_cluster rabbit@%s" % rabbit_node1)

@task
@roles('rabbit')
def verify_cluster_status(retry='yes'):

    # Retry a few times, as rabbit-mq can fail intermittently when trying to
    # connect to AMQP server. Total wait time here is atmost a minute.
    rabbitmq_up = False
    for i in range(0, 6):
        with settings(warn_only=True):
            status = sudo("service rabbitmq-server status | head -10")
        if 'running' in status.lower():
            rabbitmq_up = True
            break
        elif retry == 'no':
            return False
        time.sleep(10)
    if not rabbitmq_up:
        return False

    rabbitmq_up = False
    for i in range(0, 6):
        with settings(warn_only=True):
            output = sudo("rabbitmqctl cluster_status")
        running_nodes = re.compile(r"running_nodes,\[([^\]]*)")
        match = running_nodes.search(output)
        if match:
            rabbitmq_up = True
            break
        elif retry == 'no':
            return False
        time.sleep(10)
    if not rabbitmq_up:
        return False

    clustered_nodes = match.group(1).split(',')
    clustered_nodes = [node.strip(' \n\r\'') for node in clustered_nodes]

    rabbit_nodes = []
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string):
            if len(env.roledefs['rabbit']) <= 1 and detect_ostype() == 'redhat':
                print "Skip verifying /etc/rabbitmq/rabbitmq.config for Single node setup"
            elif not files.exists("/etc/rabbitmq/rabbitmq.config"):
                return False
            host_name = sudo('hostname -s') + ctrl
            rabbit_nodes.append('rabbit@%s' % host_name)
    for rabbit_node in rabbit_nodes:
        if rabbit_node not in clustered_nodes:
            print "RabbitMQ cluster doesnt list %s in running_nodes" % env.host_string
            return False
    return True

@task
@roles('rabbit')
def set_ha_policy_in_rabbitmq():
    sudo("rabbitmqctl set_policy HA-all \"\" '{\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}'")

@task
@roles('build')
def purge_node_from_rabbitmq_cluster(del_rabbitmq_node, role):

    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'no' and\
                             role == 'openstack':
        # We are not managing the RabbitMQ server. No-op.
        return

    if get_contrail_internal_vip() != get_openstack_internal_vip() and\
       role == 'cfgm':
        # Openstack and Contrail are in two different nodes. Cfgm
        # rabbitmq will point to the Openstack node. No-op.
        return

    env.roledefs['rabbit'] = env.roledefs[role]
    del_rabbitmq_ip = hstr_to_ip(del_rabbitmq_node)
    del_rabbitmq_ctrl_ip = hstr_to_ip(get_control_host_string(del_rabbitmq_node))
    if ping_test(del_rabbitmq_node):
        with settings(host_string = del_rabbitmq_node, warn_only = True):
            sudo("rabbitmqctl stop_app")
            sudo("rabbitmqctl reset")
            sudo("service supervisor-support-service stop")
            sudo("mv /var/lib/rabbitmq/.erlang.cookie /var/lib/rabbitmq/.erlang.cookie.removed")
            sudo("mv /etc/rabbitmq/rabbitmq.config /etc/rabbitmq/rabbitmq.config.removed")
    else:
        # If the node is not reachable, then delete the node remotely from one
        # of the nodes in the cluster.
        with settings(host_string = env.roledefs['rabbit'][0], warn_only = True):
            hostname = local('getent hosts %s | awk \'{print $3\'}' % del_rabbitmq_ctrl_ip, capture = True)
            sudo("rabbitmqctl forget_cluster_node rabbit@%s" % hostname)

    # Giving some time for the other nodes to re-adjust the cluster, 
    time.sleep(30)

    execute(config_rabbitmq)
    for host_string in env.roledefs[role]:
        with settings(host_string = host_string):
            sudo("service rabbitmq-server restart")
            # Give time for RabbitMQ to recluster
            time.sleep(30)

    result = execute(verify_cluster_status)
    if False in result.values():
        print "Unable to recluster RabbitMQ cluster after removing the node %s" % del_rabbitmq_node
        exit(1)

@task
@roles('build')
def join_rabbitmq_cluster(new_ctrl_host):
    """ Task to join a new rabbit server into an existing cluster """
    # Provision rabbitmq cluster in cfgm role nodes.
    amqp_roles = ['cfgm']
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        #Provision rabbitmq cluster in openstack role nodes aswell.
        amqp_roles.append('openstack')
    for role in amqp_roles:
        env.roledefs['rabbit'] = env.roledefs[role]

        # copy the erlang cookie from one of the other nodes.
        rabbitmq_cluster_uuid = None
        for host_string in env.roledefs['rabbit']:
            with settings(host_string=host_string, warn_only=True):
                if host_string != new_ctrl_host and\
                   sudo('ls /var/lib/rabbitmq/.erlang.cookie').succeeded:
                    rabbitmq_cluster_uuid = \
                        sudo('cat /var/lib/rabbitmq/.erlang.cookie')
                    break;
        if rabbitmq_cluster_uuid is None:
            raise RuntimeError("Not able to get the Erlang cookie from the cluster nodes")

        if not is_xenial_or_above():
            execute(listen_at_supervisor_support_port_node, new_ctrl_host)
        execute(remove_mnesia_database_node, new_ctrl_host)
        execute(verify_rabbit_node_hostname)
        execute(allow_rabbitmq_port_node, new_ctrl_host)
        execute(rabbitmq_env)
        execute(config_rabbitmq)
        execute('stop_rabbitmq_and_set_cookie_node', rabbitmq_cluster_uuid, new_ctrl_host)
        execute('start_rabbitmq_node', new_ctrl_host)
        # adding sleep to workaround rabbitmq bug 26370 prevent
        # "rabbitmqctl cluster_status" from breaking the database,
        # this is seen in ci
        time.sleep(30)
        if (role is 'openstack' and get_openstack_internal_vip() or
            role is 'cfgm' and get_contrail_internal_vip()):
            execute('set_ha_policy_in_rabbitmq')
            execute('set_tcp_keepalive')

        result = execute(verify_cluster_status)
        if False in result.values():
            print "Unable to setup RabbitMQ cluster in role[%s]...." % role
            exit(1)

@task
@roles('build')
def setup_rabbitmq_cluster(force=False):
    """Task to cluster the rabbit servers."""
    amqp_roles = []
    rabbit_servers = get_from_testbed_dict('cfgm', 'amqp_hosts', None)
    if rabbit_servers:
        print "Using external rabbitmq servers %s" % rabbit_servers
    else:
        # Provision rabbitmq cluster in cfgm role nodes.
        print "Provisioning rabbitq in cfgm nodes"
        amqp_roles = ['cfgm']

    # Provision rabbitmq cluster in openstack on request
    if get_from_testbed_dict('openstack', 'manage_amqp', 'no') == 'yes':
        # Provision rabbitmq cluster in openstack role nodes aswell.
        amqp_roles.append('openstack')

    for role in amqp_roles:
        env.roledefs['rabbit'] = env.roledefs[role]

        if not force:
            with settings(warn_only=True):
                result = execute("verify_cluster_status", retry='no')
            if result and False not in result.values():
                print "RabbitMQ cluster is up and running in role[%s]; No need to cluster again." % role
                continue

        rabbitmq_cluster_uuid = getattr(testbed, 'rabbitmq_cluster_uuid', None)
        if not rabbitmq_cluster_uuid:
            rabbitmq_cluster_uuid = uuid.uuid4()

        if not is_xenial_or_above():
            execute(listen_at_supervisor_support_port)
        execute(remove_mnesia_database)
        execute(verify_rabbit_node_hostname)
        execute(allow_rabbitmq_port)
        execute(rabbitmq_env)
        execute(config_rabbitmq)
        execute("stop_rabbitmq_and_set_cookie", rabbitmq_cluster_uuid)
        execute(start_rabbitmq)
        # adding sleep to workaround rabbitmq bug 26370 prevent
        # "rabbitmqctl cluster_status" from breaking the database,
        # this is seen in ci
        time.sleep(60)
        #execute(rabbitmqctl_stop_app)
        #execute(rabbitmqctl_reset)
        #execute("rabbitmqctl_start_app_node", env.roledefs['rabbit'][0])
        #execute(add_node_to_rabbitmq_cluster)
        #execute(rabbitmqctl_start_app)
        if (role is 'openstack' and get_openstack_internal_vip() or
            role is 'cfgm' and get_contrail_internal_vip()):
            execute('set_ha_policy_in_rabbitmq')
            execute('set_tcp_keepalive')
            execute('set_tcp_keepalive_on_compute')
        result = execute(verify_cluster_status)
        if False in result.values():
            print "Unable to setup RabbitMQ cluster in role[%s]...." % role
            exit(1)

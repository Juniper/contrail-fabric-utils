import uuid
import re
import time

from fabfile.config import *
from fabfile.templates import rabbitmq_config, rabbitmq_config_single_node, rabbitmq_env_conf
from fabfile.utils.fabos import detect_ostype
from fabfile.tasks.helpers import disable_iptables
from fabfile.utils.host import get_from_testbed_dict, get_control_host_string,\
                               hstr_to_ip, get_openstack_internal_vip,\
                               get_contrail_internal_vip

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
            sudo("sed -i 's/net.ipv4.tcp_keepalive_time\s\s*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_probes\s\s*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_intvl\s\s*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")


@task
@EXECUTE_TASK
@roles('compute')
def set_tcp_keepalive_on_compute():
    with settings(hide('stderr'), warn_only=True):
        if sudo("grep '^net.ipv4.tcp_keepalive_time' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_time = 10' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_time\s\s*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_probes\s\s*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if sudo("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            sudo("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            sudo("sed -i 's/net.ipv4.tcp_keepalive_intvl\s\s*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")

@task
@EXECUTE_TASK
@roles('rabbit')
def listen_at_supervisor_support_port():
    with settings(warn_only=True):
        if sudo("service supervisor-support-service status | grep running").failed:
            sudo("service supervisor-support-service start")
            sudo("supervisorctl -s unix:///tmp/supervisord_support_service.sock stop all")

@task
@EXECUTE_TASK
@roles('rabbit')
def remove_mnesia_database():
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
    with settings(host_string=env.host_string, password=env.passwords[env.host_string]):
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
        with settings(host_string=host_string, password=env.passwords[host_string]):
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
    execute('disable_iptables')

@task
@parallel
@roles('rabbit')
def stop_rabbitmq_and_set_cookie(uuid):
     with settings(warn_only=True):
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
        with settings(warn_only=(retry == 'yes')):
            status = sudo("service rabbitmq-server status")
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
        with settings(warn_only=(retry == 'yes')):
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
@task
def set_ha_policy_in_rabbitmq():
    sudo("rabbitmqctl set_policy HA-all \"\" '{\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}'")

@task
@roles('build')
def setup_rabbitmq_cluster(force=False):
    """Task to cluster the rabbit servers."""
    # Provision rabbitmq cluster in cfgm role nodes.
    amqp_roles = ['cfgm']
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

        execute(listen_at_supervisor_support_port)
        execute(remove_mnesia_database)
        execute(verify_rabbit_node_hostname)
        execute(allow_rabbitmq_port)
        execute(rabbitmq_env)
        execute(config_rabbitmq)
        execute("stop_rabbitmq_and_set_cookie", rabbitmq_cluster_uuid)
        execute(start_rabbitmq)
        #adding sleep to workaround rabbitmq bug 26370 prevent "rabbitmqctl cluster_status" from breaking the database, this is seen in ci
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

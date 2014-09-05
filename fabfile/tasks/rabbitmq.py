import uuid
import re

from fabfile.config import *
from fabfile.templates import rabbitmq_config, rabbitmq_config_single_node
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import get_from_testbed_dict, get_control_host_string,\
                               hstr_to_ip, get_openstack_internal_vip


def verfiy_and_update_hosts(host_name, host_string):
    with settings(warn_only=True):
        resolved = run("ping -c 1 %s | grep '1 received'" % host_name).succeeded
    if not resolved:
        run("echo '%s          %s' >> /etc/hosts" % (host_string.split('@')[1], host_name))

@task
@EXECUTE_TASK
@roles('rabbit')
def set_tcp_keepalive():
    with settings(hide('stderr'), warn_only=True):
        if run("grep '^net.ipv4.tcp_keepalive_time' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_time = 5' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_time\s\s*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if run("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_probes\s\s*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if run("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_intvl\s\s*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")


@task
@EXECUTE_TASK
@roles('compute')
def set_tcp_keepalive_on_compute():
    with settings(hide('stderr'), warn_only=True):
        if run("grep '^net.ipv4.tcp_keepalive_time' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_time = 10' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_time\s\s*/net.ipv4.tcp_keepalive_time = 5/' /etc/sysctl.conf")

        if run("grep '^net.ipv4.tcp_keepalive_probes' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_probes = 5' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_probes\s\s*/net.ipv4.tcp_keepalive_probes = 5/' /etc/sysctl.conf")

        if run("grep '^net.ipv4.tcp_keepalive_intvl' /etc/sysctl.conf").failed:
            run("echo 'net.ipv4.tcp_keepalive_intvl = 1' >> /etc/sysctl.conf")
        else:
            run("sed -i 's/net.ipv4.tcp_keepalive_intvl\s\s*/net.ipv4.tcp_keepalive_intvl = 1/' /etc/sysctl.conf")

@task
@EXECUTE_TASK
@roles('rabbit')
def listen_at_supervisor_config_port():
    with settings(hide('everything'), warn_only=True):
        if run("service supervisor-config status | grep running").failed:
            run("service supervisor-config start")
            run("supervisorctl -s http://localhost:9004 stop all")

@task
@EXECUTE_TASK
@roles('rabbit')
def remove_mnesia_database():
    run("rm -rf /var/lib/rabbitmq/mnesia")

@task
@parallel
@roles('rabbit')
def set_guest_user_permissions():
    with settings(warn_only=True):
        run('rabbitmqctl set_permissions guest ".*" ".*" ".*"')

@task
@serial
@roles('rabbit')
def config_rabbitmq():
    rabbit_hosts = []
    rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string, password=env.passwords[host_string]):
            host_name = run('hostname')
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
    cfg_file = open(tmp_fname, 'a')
    cfg_file.write(rabbitmq_configs)
    cfg_file.close()
    put(tmp_fname, "/etc/rabbitmq/rabbitmq.config")
    local("rm %s" %(tmp_fname))

@task
@parallel
@roles('rabbit')
def allow_rabbitmq_port():
    if detect_ostype() in ['centos']:
        run("iptables --flush")
        run("service iptables save")

@task
@parallel
@roles('rabbit')
def stop_rabbitmq_and_set_cookie(uuid):
     with settings(warn_only=True):
         run("service rabbitmq-server stop")
         run("epmd -kill")
         run("rm -rf /var/lib/rabbitmq/mnesia/")
     run("echo '%s' > /var/lib/rabbitmq/.erlang.cookie" % uuid)


@task
@serial
@roles('rabbit')
def start_rabbitmq():
     run("service rabbitmq-server restart")

@task
@parallel
@roles('rabbit')
def rabbitmqctl_stop_app():
    run("rabbitmqctl stop_app")

@task
@parallel
@roles('rabbit')
def rabbitmqctl_reset():
    run("rabbitmqctl force_reset")

@task
@parallel
@hosts(*env.roledefs['rabbit'][1:])
def rabbitmqctl_start_app():
    execute("rabbitmqctl_start_app_node", env.host_string)

@task
def rabbitmqctl_start_app_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            run("rabbitmqctl start_app")

@task
@roles('rabbit')
def verify_rabbit_node_hostname():
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string):
            host_name = run('hostname')
        verfiy_and_update_hosts(host_name, host_string)

@task
@hosts(*env.roledefs['rabbit'][1:])
def add_node_to_rabbitmq_cluster():
    with settings(host_string=env.roledefs['rabbit'][0]):
        rabbit_node1 = run('hostname')
    this_rabbit_node = run('hostname')
    run("rabbitmqctl join_cluster rabbit@%s" % rabbit_node1)

@task
@roles('rabbit')
def verify_cluster_status():
    output = run("rabbitmqctl cluster_status")
    running_nodes = re.compile(r"running_nodes,\[([^\]]*)")
    match = running_nodes.search(output)
    if not match:
        return False
    clustered_nodes = match.group(1).split(',')
    clustered_nodes = [node.strip(' \n\r\'') for node in clustered_nodes]

    rabbit_nodes = []
    for host_string in env.roledefs['rabbit']:
        with settings(host_string=host_string):
            if not files.exists("/etc/rabbitmq/rabbitmq.config"):
                return False
            host_name = run('hostname')
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
    run("rabbitmqctl set_policy HA-all \"\" '{\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}'")

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
                result = execute(verify_cluster_status)
            if result and False not in result.values():
                print "RabbitMQ cluster is up and running in role[%s]; No need to cluster again." % role
                continue

        rabbitmq_cluster_uuid = getattr(testbed, 'rabbitmq_cluster_uuid', None)
        if not rabbitmq_cluster_uuid:
            rabbitmq_cluster_uuid = uuid.uuid4()

        execute(listen_at_supervisor_config_port)
        execute(remove_mnesia_database)
        execute(verify_rabbit_node_hostname)
        execute(allow_rabbitmq_port)
        execute(config_rabbitmq)
        execute("stop_rabbitmq_and_set_cookie", rabbitmq_cluster_uuid)
        execute(start_rabbitmq)
        if len(env.roledefs['rabbit']) <= 1:
            print "Single cfgm cluster, Starting rabbitmq."
            return
        #execute(rabbitmqctl_stop_app)
        #execute(rabbitmqctl_reset)
        #execute("rabbitmqctl_start_app_node", env.roledefs['rabbit'][0])
        #execute(add_node_to_rabbitmq_cluster)
        #execute(rabbitmqctl_start_app)
        if get_openstack_internal_vip():
            execute('set_ha_policy_in_rabbitmq')
            execute('set_tcp_keepalive')
            execute('set_tcp_keepalive_on_compute')
        result = execute(verify_cluster_status)
        if False in result.values():
            print "Unable to setup RabbitMQ cluster in role[%s]...." % role
            exit(1)

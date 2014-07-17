import uuid
import re

from fabfile.config import *
from fabfile.templates import rabbitmq_config
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import get_from_testbed_dict, get_control_host_string,\
                               hstr_to_ip


def verfiy_and_update_hosts(host_name, host_string):
    with settings(warn_only=True):
        resolved = run("ping -c 1 %s | grep '1 received'" % host_name).succeeded
    if not resolved:
        run("echo '%s          %s' >> /etc/hosts" % (host_string.split('@')[1], host_name))

@task
@EXECUTE_TASK
@roles('cfgm')
def listen_at_supervisor_config_port():
    with settings(hide('everything'), warn_only=True):
        run("service supervisor-config start")
        run("supervisorctl -s http://localhost:9004 stop all")

@task
@EXECUTE_TASK
@roles('cfgm')
def remove_mnesia_database():
    run("rm -rf /var/lib/rabbitmq/mnesia")

@task
@parallel
@roles('cfgm')
def set_guest_user_permissions():
    with settings(warn_only=True):
        run('rabbitmqctl set_permissions guest ".*" ".*" ".*"')

@task
@serial
@roles('cfgm')
def config_rabbitmq():
    rabbit_hosts = []
    rabbit_conf = '/etc/rabbitmq/rabbitmq.config'
    for host_string in env.roledefs['cfgm']:
        with settings(host_string=host_string, password=env.passwords[host_string]):
            host_name = run('hostname')
        rabbit_hosts.append("\'rabbit@%s\'" % host_name)
    rabbit_hosts = ', '.join(rabbit_hosts)
    rabbitmq_configs = rabbitmq_config.template.safe_substitute({
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
@roles('cfgm')
def allow_rabbitmq_port():
    if detect_ostype() in ['centos']:
        run("iptables --flush")
        run("service iptables save")

@task
@parallel
@roles('cfgm')
def stop_rabbitmq_and_set_cookie(uuid):
     with settings(warn_only=True):
         run("service rabbitmq-server stop")
         run("epmd -kill")
         run("rm -rf /var/lib/rabbitmq/mnesia/")
     run("echo '%s' > /var/lib/rabbitmq/.erlang.cookie" % uuid)


@task
@serial
@roles('cfgm')
def start_rabbitmq():
     run("service rabbitmq-server restart")

@task
@parallel
@roles('cfgm')
def rabbitmqctl_stop_app():
    run("rabbitmqctl stop_app")

@task
@parallel
@roles('cfgm')
def rabbitmqctl_reset():
    run("rabbitmqctl force_reset")

@task
@parallel
@hosts(*env.roledefs['cfgm'][1:])
def rabbitmqctl_start_app():
    execute("rabbitmqctl_start_app_node", env.host_string)

@task
def rabbitmqctl_start_app_node(*args):
    for host_string in args:
        with settings(host_string=host_string):
            run("rabbitmqctl start_app")

@task
@roles('cfgm')
def verify_cfgm_hostname():
    for host_string in env.roledefs['cfgm']:
        with settings(host_string=host_string):
            host_name = run('hostname')
        verfiy_and_update_hosts(host_name, host_string)

@task
@hosts(*env.roledefs['cfgm'][1:])
def add_cfgm_to_rabbitmq_cluster():
    with settings(host_string=env.roledefs['cfgm'][0]):
        cfgm1 = run('hostname')
    this_cfgm = run('hostname')
    run("rabbitmqctl join_cluster rabbit@%s" % cfgm1)

@task
@roles('cfgm')
def verify_cluster_status():
    output = run("rabbitmqctl cluster_status")
    running_nodes = re.compile(r"running_nodes,\[([^\]]*)")
    match = running_nodes.search(output)
    if not match:
        return False
    clustered_nodes = match.group(1).split(',')
    clustered_nodes = [node.strip(' \n\r\'') for node in clustered_nodes]

    cfgms = []
    for host_string in env.roledefs['cfgm']:
        with settings(host_string=host_string):
            host_name = run('hostname')
            cfgms.append('rabbit@%s' % host_name)
    for cfgm in cfgms:
        if cfgm not in clustered_nodes:
            print "RabbitMQ cluster doesnt list %s in running_nodes" % env.host_string
            return False
    return True

@task
@roles('cfgm')
@task
def set_ha_policy_in_rabbitmq():
    run("rabbitmqctl set_policy HA-all \"\" '{\"ha-mode\":\"all\",\"ha-sync-mode\":\"automatic\"}'")

@task
@roles('build')
def setup_rabbitmq_cluster(force=False):
    """Task to cluster the rabbit servers."""
    if len(env.roledefs['cfgm']) <= 1:
        print "Single cfgm cluster, skipping rabbitmq cluster setup."
        return 

    if not force:
        with settings(warn_only=True):
            result = execute(verify_cluster_status)
        if result and False not in result.values():
            print "RabbitMQ cluster is up and running; No need to cluster again."
            return

    rabbitmq_cluster_uuid = getattr(testbed, 'rabbitmq_cluster_uuid', None)
    if not rabbitmq_cluster_uuid:
        rabbitmq_cluster_uuid = uuid.uuid4()

    execute(listen_at_supervisor_config_port)
    execute(remove_mnesia_database)
    execute(verify_cfgm_hostname)
    execute(allow_rabbitmq_port)
    execute(config_rabbitmq)
    execute("stop_rabbitmq_and_set_cookie", rabbitmq_cluster_uuid)
    execute(start_rabbitmq)
    #execute(rabbitmqctl_stop_app)
    #execute(rabbitmqctl_reset)
    #execute("rabbitmqctl_start_app_node", env.roledefs['cfgm'][0])
    #execute(add_cfgm_to_rabbitmq_cluster)
    #execute(rabbitmqctl_start_app)
    if get_from_testbed_dict('ha', 'internal_vip', None):
        execute('set_ha_policy_in_rabbitmq')
    result = execute(verify_cluster_status)
    if False in result.values():
        print "Unable to setup RabbitMQ cluster...."
        exit(1)

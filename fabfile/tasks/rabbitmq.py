import uuid
import re
import time

from fabfile.config import *
from fabfile.utils.host import get_from_testbed_dict, get_control_host_string,\
    hstr_to_ip, get_openstack_internal_vip, get_contrail_internal_vip,\
    get_env_passwords

@task
@serial
@roles('rabbit')
def setup_amqp(role, cookie, rabbit_hosts, rabbit_hosts_ip, force):
    self_ip = hstr_to_ip(get_control_host_string(env.host_string))
    cmd = 'setup-vnc-amqp'
    cmd += ' --self_ip %s' % self_ip
    cmd += ' --cookie %s' % cookie
    cmd += ' --amqp_hosts %s' % ' '.join(rabbit_hosts)
    cmd += ' --amqp_hosts_ip %s' % ' '.join(rabbit_hosts_ip)
    cmd += ' --role %s' % role
    if force:
        cmd += ' --force'
    internal_vip = get_openstack_internal_vip()
    if internal_vip:
        # Highly available setup
        cmd += ' --internal_vip %s' % (internal_vip)
    contrail_internal_vip = get_contrail_internal_vip()
    if contrail_internal_vip:
        # Highly available setup with multiple interface
        cmd += ' --contrail_internal_vip %s' % (contrail_internal_vip)
    # Last node in amqp cluster, After provisioning make sure
    #  all nodes are in cluster
    if (env.roledefs[role].index(env.host_string) + 1 ==
        len(env.roledefs[role])):
        cmd += ' --verify_all'
    sudo(cmd)

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
        rabbit_hosts = []
        rabbit_hosts_ip = []
        for host_string in env.roledefs[role]:
            with settings(host_string=host_string,
                          password=get_env_passwords(host_string)):
                rabbit_hosts.append(sudo('hostname -s'))
                rabbit_hosts_ip.append(\
                    hstr_to_ip(get_control_host_string(host_string)))

        rabbitmq_cluster_uuid = getattr(testbed, 'rabbitmq_cluster_uuid', None)
        if not rabbitmq_cluster_uuid:
            rabbitmq_cluster_uuid = uuid.uuid4()

        execute('setup_amqp', role, rabbitmq_cluster_uuid, rabbit_hosts,
                                  rabbit_hosts_ip, force)

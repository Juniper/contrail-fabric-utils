"""Private contrail task for setting up RDO in the openstack node."""

from fabfile.config import *


@task
@roles('openstack')
def fix_yum_repos():
    """Fix the yum repos to point to locat repos."""
    run('printf "\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "[redhat_all_rpms]\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "name=redhat_all_rpms\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "baseurl=http://10.84.5.100/redhat_all_rpms\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "enabled=1\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "priority=99\n" >> /etc/yum.repos.d/cobbler-config.repo')
    run('printf "gpgcheck=0\n" >> /etc/yum.repos.d/cobbler-config.repo')
    with settings(warn_only=True):
        if run('ls /etc/yum.repos.d/rdo-release.repo').succeeded:
            run('mv /etc/yum.repos.d/rdo-release.repo /etc/yum.repos.d/rdo-release.repo.backup')
        if run('ls /etc/yum.repos.d/epel-testing.repo').succeeded:
            run('mv /etc/yum.repos.d/epel-testing.repo /etc/yum.repos.d/epel-testing.repo.backup')
        if run('ls /etc/yum.repos.d/rdo-release.repo').succeeded:
            run('mv /etc/yum.repos.d/epel.repo /etc/yum.repos.d/epel.repo.backup')
    run('yum clean all')

@task
@roles('openstack')
def setup_rdo(rdo='rdo-release-grizzly-3.noarch.rpm'):
    """Set up RDO in the openstack node"""
    with settings(warn_only=True):
        run('sudo yum install -y http://repos.fedorapeople.org/repos/openstack/openstack-grizzly/%s' % rdo)
    execute(fix_yum_repos)
    with settings(warn_only=True):
        run('sudo yum install -y openstack-packstack')
    run('yes %s | packstack --allinone --mysql-pw juniper123' % env.passwords[env.host_string])
    openstack_password = getattr(env, 'openstack_admin_password', 'contrail123')
    run('source keystonerc_admin && keystone user-password-update --pass %s admin' % openstack_password)
    run("sed -i -e 's/export OS_PASSWORD=.*/export OS_PASSWORD=%s/' keystonerc_admin " % openstack_password)

    steps = "\n\n\n"
    steps += "="*160
    steps += "\nSteps to bring up contrail with the RDO:\n\
                1. Get the admin_token from /etc/keystone/keystone.conf of the openstack node and populate it as service_token in the testbed.py.\n\
                2. fab install_without_openstack (This step can be executed even before fab setup_rdo)\n\
                3. fab setup_without_openstack\n"
    steps += "="*160
    print steps

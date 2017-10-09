import re

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_linux_distro,\
        get_contrail_containers, put_to_container, run_in_container
from fabfile.utils.cluster import get_orchestrator

@task
@EXECUTE_TASK
@roles('all')
def install_test_repo():
    '''
    Installs test repo which contains packages specific to
    execute contrail test scripts
    '''
    containers = get_contrail_containers()
    for container in containers:
        execute('install_test_repo_node', container, env.host_string)
    if env.host_string in env.roledefs['compute'] and \
            'openstack' in get_orchestrator():
        execute('install_test_repo_node', None, env.host_string)


@task
def install_test_repo_node(container=None, *args):
    '''Installs test repo in given node'''
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            trusty_repo = 'fabfile/contraillabs/repo/trusty_test.list'
            xenial_repo = 'fabfile/contraillabs/repo/xenial_test.list'
            ubuntu_repo_dest = '/etc/apt/sources.list.d/test_repo.list'
            el7_repo = 'fabfile/contraillabs/repo/centos_el7_test.repo'
            rh_repo = 'fabfile/contraillabs/repo/el7_test.repo'
            rh_repo_dest = '/etc/yum.repos.d/contrail_test.repo'
            if container:
                os_type, version, extra = get_linux_distro(container=container)
                os_type = os_type.lower()
                extra = extra.lower()
                if os_type in ['ubuntu']:
                    if 'trusty' in extra :
                        put_to_container(container, trusty_repo, ubuntu_repo_dest)
                    if 'xenial' in extra :
                        put_to_container(container, xenial_repo, ubuntu_repo_dest)
                    run_in_container(container, 'apt-get update')
                if os_type in ['centos', 'centoslinux']:
                    put_to_container(container, el7_repo, rh_repo_dest)
                    run_in_container(container, 'yum clean all')
                if os_type in ['redhat']:
                    put_to_container(container, rh_repo, rh_repo_dest)
                    run_in_container(container, 'yum clean all')
            else:
                os_type, version, extra = get_linux_distro()
                os_type = os_type.lower()
                extra = extra.lower()
                if os_type in ['ubuntu']:
                    if 'trusty' in extra :
                        put(trusty_repo, ubuntu_repo_dest)
                    if 'xenial' in extra :
                        put(xenial_repo, ubuntu_repo_dest)
                    sudo('apt-get update')
                if os_type in ['centos', 'centoslinux']:
                    put(el7_repo, rh_repo_dest)
                    sudo('yum clean all')
                if os_type in ['redhat']:
                    put(rh_repo, rh_repo_dest)
                    sudo('yum clean all')
            # endif



@task
@EXECUTE_TASK
@roles('all')
def cleanup_repo():
    '''Removes all existing repos in all the nodes specified in testbed'''
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            if env.host_string == esxi_hosts[esxi]['contrail_vm']['host']:
                return
    execute('cleanup_repo_node', env.host_string)

@task
def cleanup_repo_node(*args):
    '''Remove existing repos in given node'''
    for host_string in args:
        with settings(host_string=host_string):
            os_type = detect_ostype().lower()
            with hide('everything'):
                ts = sudo("date '+%s'")
            if os_type == 'ubuntu':
                org_repo_file = '/etc/apt/sources.list'
                bck_repo_file = '/etc/apt/sources.list.%s.contrail' % ts
                print 'Backup Original sources.list (%s) as (%s)' % (
                    org_repo_file, bck_repo_file)
                sudo('mv %s %s' % (org_repo_file, bck_repo_file))
                print 'Create an empty sources.list'
                sudo('touch /etc/apt/sources.list')
                sudo('echo >> /etc/apt/sources.list')
                sudo('chmod 644 /etc/apt/sources.list')
                sudo('apt-get update')
            elif os_type in ['centos', 'redhat', 'centoslinux']:
                with cd('/etc/yum.repos.d/'):
                    with settings(warn_only=True):
                        with hide('everything'):
                            repo_files = run('ls -1 *.repo').split('\r\n')
                        print 'Backup Original repo files with timestamp'
                        for repo_file in repo_files:
                            sudo('mv %s %s.%s.contrail' % (repo_file,
                                 repo_file, ts))
                        sudo('yum clean all')

@task
@EXECUTE_TASK
@roles('all')
def restore_repo(merge=True):
    '''Removes all existing repos in all the nodes specified in testbed'''
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            try:
                if env.host_string == esxi_hosts[esxi]['contrail_vm']['host']:
                    return
            except Exception as e:
                #For vrouter gateway,contrail-vm does not exist
                print ('Vrouter gateway setup.contrail_vm does not exist.restore repo skipped..')
                return
    execute('restore_repo_node', env.host_string)

@task
def restore_repo_node(*args, **kwargs):
    '''Remove existing repos in given node'''
    merge = kwargs.get('merge', True)
    pattern = re.compile(r'\.[\d]+\.contrail$')
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            os_type = detect_ostype().lower()
            if os_type == 'ubuntu':
                dirname = '/etc/apt'
                update_cmd = 'apt-get update'
            else:
                dirname = '/etc/yum.repos.d/'
                update_cmd = 'yum clean all'

            with cd(dirname):
                repo_files = sudo("find . -maxdepth 1 -regextype sed \
                                          -regex '.*/*[0-9]*\.contrail'")
                repo_files = repo_files.split('\r\n')
                restore_map = [(repo_file, pattern.sub('', repo_file)) \
                                  for repo_file in repo_files]
                for original, restore_file in restore_map:
                    sudo('cp %s %s.oldbckup' % (original, original))
                    if merge == True:
                        sudo('cat %s >> %s' % (original, restore_file)) 
                    else:
                        sudo('mv %s %s' % (original, restore_file))
                    sudo('chmod 644 %s' % restore_file)
                sudo(update_cmd)

@task
def update_keystone_admin_token():
    '''Retrieve admin token from openstack node (/etc/keystone/keystone.conf)
       and update it in testbed.py'''
    openstack_node = testbed.env['roledefs']['openstack'][0]
    with settings(host_string=openstack_node):
        admin_token = run('echo "ADMING_KEY: $(grep -Po "^admin_token\s*=\s*\K\w+" /etc/keystone/keystone.conf)" | grep -Po "ADMING_KEY: \K\w+"')
    local('sed -i "s/\'admin_token\'.*/\'admin_token\' : \'%s\',/g" fabfile/testbeds/testbed.py' % admin_token)
    local('sed -i "s/\'service_token\'.*/\'service_token\' : \'%s\',/g" fabfile/testbeds/testbed.py' % admin_token)


@task
def centos7_kilo_test_repo(action='create'):
    '''Add local centos7 kilo repo to server packages needed for sanity
    '''
    if action == 'create':
        put('fabfile/contraillabs/repo/centos7_kilo_test.repo', '/etc/yum.repos.d/centos7_kilo_test.repo', use_sudo=True)
    elif action == 'delete':
        with settings(warn_only=True):
            sudo('rm -f /etc/yum.repos.d/centos7_kilo_test.repo')
    else:
        print "WARNING: Unknown Action (%s)" % action
    sudo('yum clean all')

@task
def rhel7_kilo_test_repo(action='create'):
    '''Add local rhel7 kilo repo to server packages needed for sanity
    '''
    if action == 'create':
        put('fabfile/contraillabs/repo/rhel7_kilo_test.repo', '/etc/yum.repos.d/rhel7_kilo_test.repo', use_sudo=True)
    elif action == 'delete':
        with settings(warn_only=True):
            sudo('rm -f /etc/yum.repos.d/rhel7_kilo_test.repo')
    else:
        print "WARNING: Unknown Action (%s)" % action
    sudo('yum clean all')

@task
@EXECUTE_TASK
@roles('all')
def subscribe_rhel_repos(username, password, rhosp_version='7.0'):
    repo_list = ['rhel-7-server-extras-rpms', 'rhel-7-server-optional-rpms',
                 'rhel-7-server-rpms', 'rhel-7-server-openstack-%s-rpms' % rhosp_version]
    sudo('subscription-manager register --force \
                                        --username %s \
                                        --password %s' % (username, password))
    sudo('subscription-manager attach --auto')
    for reponame in repo_list:
        sudo('subscription-manager repos --enable=%s' % reponame)

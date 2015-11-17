import re

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype

@task
@EXECUTE_TASK
@roles('all')
def install_test_repo():
    '''Installs test repo which contains packages specific to
       execute contrail test scripts
    '''
    execute('install_test_repo_node', env.host_string)

@task
def install_test_repo_node(*args):
    '''Installs test repo in given node'''
    for host_string in args:
        with settings(host_string=host_string):
            os_type = detect_ostype().lower()
            if os_type in ['ubuntu']:
                print 'No test-repo availabe'
            if os_type in ['centos']:
                print 'No test-repo availabe'
            if os_type in ['redhat']:
                put('fabfile/contraillabs/repo/el7_test.repo',
                    '/etc/yum.repos.d/contrail_test.repo')
                run('yum clean all')


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
            if env.host_string == esxi_hosts[esxi]['contrail_vm']['host']:
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
        admin_token = run('echo "ADMING_KEY: $(grep -Po "^admin_token=\K\w+" /etc/keystone/keystone.conf)" | grep -Po "ADMING_KEY: \K\w+"')
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

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype

@task
@EXECUTE_TASK
@roles('all')
def install_test_repo():
    '''Installs test repo which contains packages specific to execute contrail test scripts'''
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
    execute('cleanup_repo_node', env.host_string)

@task
def cleanup_repo_node(*args):
    '''Remove existing repos in given node'''
    for host_string in args:
        with settings(host_string=host_string):
            os_type = detect_ostype().lower()
            with hide('everything'):
                ts = run("date '+%s'")
            if os_type == 'ubuntu':
                org_repo_file = '/etc/apt/sources.list'
                bck_repo_file = '/etc/apt/sources_%s.list' % ts
                print 'Backup Original sources.list (%s) as (%s)' % (
                    org_repo_file, bck_repo_file)
                run('mv %s %s' % (org_repo_file, bck_repo_file))
                print 'Create an empty sources.list'
                run('touch /etc/apt/sources.list')
                run('chmod 644 /etc/apt/sources.list')
                run('apt-get update')
            elif os_type in ['centos', 'redhat']:
                with cd('/etc/yum.repos.d/'):
                    with settings(warn_only=True):
                        with hide('everything'):
                            repo_files = run('ls -1 *.repo').split('\r\n')
                        print 'Backup Original repo files with timestamp'
                        for repo_file in repo_files:
                            run('mv %s %s.%s' % (repo_file, repo_file, ts))
                        run('yum clean all')

@task
def update_keystone_admin_token():
    openstack_node = testbed.env['roledefs']['openstack'][0]
    with settings(host_string=openstack_node):
        admin_token = run('echo "ADMING_KEY: $(grep -Po "^admin_token=\K\w+" /etc/keystone/keystone.conf)" | grep -Po "ADMING_KEY: \K\w+"')
    local('sed -i "s/\'admin_token\'.*/\'admin_token\' : \'%s\',/g" fabfile/testbeds/testbed.py' % admin_token)
    local('sed -i "s/\'service_token\'.*/\'service_token\' : \'%s\',/g" fabfile/testbeds/testbed.py' % admin_token)

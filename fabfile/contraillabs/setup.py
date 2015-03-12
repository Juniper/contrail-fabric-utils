#!/usr/bin/env python
import os
import os.path

from fabfile.config import *
import fabfile.common as common
from fabfile.utils.host import verify_sshd, get_env_passwords

@task
@parallel
@roles('all')
def check_reimage_status():
    user, hostip = env.host_string.split('@')
    print 'Reimage issued; Waiting for the node (%s) to go down...' % hostip
    common.wait_until_host_down(wait=300, host=hostip)
    print 'Node (%s) is down... Waiting for node to come back up' % hostip
    sys.stdout.write('.')
    while not verify_sshd(hostip,
                          user,
                          get_env_passwords(env.host_string)):
        sys.stdout.write('.')
        sys.stdout.flush()
        sleep(2)
        continue

@task
@roles('build')
def bringup_test_setup(build, reimage=False):
    buildid = build
    cfgm = env.roledefs['cfgm'][0]
    if hasattr(env, 'mytestbed'):
        testbed_py = '%s.py' % env.mytestbed
    else:
        testbed_py = 'testbed.py'

    #reimage
    if os.path.isfile(build):
        fname = os.path.basename(build)
        name, ftype = os.path.splitext(fname)
        if reimage:
            if ftype in ['.rpm', '.deb']:
                execute('all_reimage')
            else:
                raise RuntimeError('Unsuported package file: %s.' % build)
            execute('check_reimage_status')
    else:
        print "Package %s not found." % build
        print "Specify a valid contrail-install-packages location."
        exit(1)
    execute('install_pkg_all', build)
    buildid = build.split('-')[-1].split('.')[0]

    #install contrail
    with settings(host_string=env.roledefs['cfgm'][0]):
        with cd('/opt/contrail/contrail_packages/'):
            sudo('./setup.sh')
        put('fabfile/testbeds/%s' % testbed_py, '/opt/contrail/utils/fabfile/testbeds/testbed.py')
        with cd('/opt/contrail/utils/'):
            sudo('pwd')
            if cfgm in env.roledefs['compute']:
                sudo('fab install_contrail:False')
                execute('compute_reboot')
            else:
                sudo('fab install_contrail')
    connections.clear()

    # setup interface
    with settings(host_string=env.roledefs['cfgm'][0]):
        with cd('/opt/contrail/utils/'):
            sudo('fab setup_interface')

    # setup all
    with settings(host_string=env.roledefs['cfgm'][0]):
        with cd('/opt/contrail/utils/'):
            sudo('pwd')
            if cfgm in env.roledefs['compute']:
                sudo('fab setup_all:False')
                execute('compute_reboot')
            else:
                sudo('fab setup_all')

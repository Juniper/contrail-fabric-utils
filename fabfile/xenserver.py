__all__ = ['reimage', 'setup', 'reimage_and_setup']

from fabric.api import *
from common import *
import socket
import tempfile
import sys

def get_host_name(ip):
    hostname, alias, ip = socket.gethostbyaddr(ip)
    return hostname.split('.')[0]

def host_string_to_ip(host_string):
    return host_string.split('@')[1]

def check_xen_version():
    if not 'xen_ver' in env:
        env.xen_ver = '6.2SP1'
    elif env.xen_ver != '6.1' and env.xen_ver != '6.2SP1':
        print "ERROR: xen_ver should be 6.1 or 6.2SP1 in testbed.py"
        sys.exit(1)
    return
#end check_xen_version

@roles('compute')
@task
def reimage():
    host = get_host_name(env.host)
    check_xen_version()
    if env.xen_ver == '6.1':
        local('/cs-shared/cf/bin/xen.reimage %s' % host)
    if env.xen_ver == '6.2SP1':
        local('/cs-shared/cf/bin/xen62.reimage %s' % host)
        
    print 'Waiting for reimage to finish...'
    wait_until_host_down()
    reconnect(1500)

    if env.xen_ver == '6.2SP1':
        print 'Applying SP1 patch...'
        if not 'xen62sp1_repo' in env:
            print 'Xen SP1 repo not set. Defaulting to the US repo'
            env.xen62sp1_repo = 'http://10.84.5.120/cs-shared/xen62sp1'
        sudo('cd /tmp && wget %s/XS62ESP1.xsupdate && wget %s/XS62ESP1-src-pkgs.tar.bz2' % (env.xen62sp1_repo, env.xen62sp1_repo))
        sudo('xe patch-upload file-name=/tmp/XS62ESP1.xsupdate')
        sudo('xe patch-pool-apply uuid=0850b186-4d47-11e3-a720-001b2151a503')
        sudo('xe patch-list name-label=XS62ESP1')
        reboot(360)


@roles('compute')
@task
def setup():
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    sudo('cd /opt/contrail/xenserver-scripts/ && sh ./contrail-setup.sh %s %s' %
        (env.config['yum_repo_host'], cfgm_ip))
    reboot(360)


@hosts('localhost')
@task
def reimage_and_setup():
    execute(reimage)
    execute(setup)


__all__ = ['install_packages', 'install_cloudstack_packages', 'install_contrail_packages', 'setup_cloud', 'install_vm_template',
           'provision_routing', 'provision_all', 'run_sanity', 'enable_proxyvm_console_access', 'cloudstack_api_setup',
           'setup_vmtemplate', 'check_systemvms', 'install_contrail', 'install_cloudstack', 'install_xenserver']

from fabric.api import env, parallel, roles, run, settings, sudo, task, cd, \
    execute, local, lcd, hide
from fabric.state import output, connections
from fabric.operations import get, put

import json
import tempfile
from urllib import urlencode, quote
import urllib2
from time import sleep
import sys
import subprocess
import re
import socket
import os

from common import *
from fabfile.utils.cluster import get_hostname

# Don't add any new testbeds here. Create new files under fabfile/testbeds
# and copy/link the testbed.py file from/to the one you want to use.
#
# Note that fabfile/testbeds/testbed.py MUST NOT be added to the repository.
import testbeds.testbed as testbed

def host_string_to_ip(host_string):
    return host_string.split('@')[1]

def render_controller_config(cfg):
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    out = cfg['cloud']
    out['nfs_share_path'] = cfg['nfs_share_path']
    if (orchestrator_ip == cfgm_ip):
        out['controller_ip'] = '127.0.0.1'
    else:
        out['controller_ip'] = host_string_to_ip(env.roledefs['orchestrator'][0])
    out['orchestrator_ip'] = orchestrator_ip
    return out

def try_login(host, username, password):
    try:
        data = urlencode([('command', 'login'), ('username', username),
                        ('password', password), ('response', 'json')])
        request = urllib2.Request('http://' + host + ':8080/client/api', data,
                                  {'Content-Type': 'application/x-www-form-urlencoded',
                                   'Accept': 'application/json'})
        out = urllib2.urlopen(request)
        if not out.read(1):
            return False
        if out.getcode() is not 200:
            return False

    except Exception as e:
        #print 'Connection to Cloudstack API error: %s' % e
        return False

    return True

def wait_for_cloudstack_management_up(host, username, password):
    timeout = 0
    while timeout <= 90:
        if try_login(host, username, password):
            return True
        sleep(10)
        timeout += 1
        if timeout == 30:
            sudo('cloudstack-setup-management')
    print 'Timeout while waiting for cloudstack-management to start up'
    sys.exit(1)

def check_cs_version_in_config():
    if 'cs_version' in env:
        print "found cs-version\n"
    else:
        print "cs-version doesnt exist\n"
        env.cs_version = '4.3.0'
#end get_cs_version_from_config

def cloudLogin(file):
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    login = ("'command=login&username=" + env.config['cloud']['username'] +
              "&password=" + env.config['cloud']['password'] + "&response=json'")
    cmd = "curl -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json'\
                    -X POST -d %s -c '%s' http://%s:8080/client/api" %(login, file, orchestrator_ip)
    output = sudo(cmd)
    response = json.loads(output)
    if not response or response.get('errorresponse'):
        if response:
            print response['errorresponse']['errortext']
        return None
    return response['loginresponse']

def getKeys(loginresp, file):
    urlParam = '&response=json&id=' + loginresp['userid'] +\
               '&sessionkey=' + encodeURIComponent(loginresp['sessionkey'])
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    cmd = "curl -H 'Content-Type: application/json' -b %s -X POST \
           'http://%s:8080/client/api/?command=listUsers%s'" %(file, orchestrator_ip, urlParam)
    output = sudo(cmd)
    response = json.loads(output)
    user = response['listusersresponse']['user'][0]
    if not 'apikey' in user:
        return None
    return user['apikey'], user['secretkey']

def encodeURIComponent(str):
    return quote(str, safe='~()*!.\'')

def updateCloudMonkeyConfig():
    if 'keysupdated' in env and env.keysupdated:
        return
    with tempfile.NamedTemporaryFile(delete=True) as file:
        response = cloudLogin(file.name)
        if not response:
            assert False, "Authentication failed"
        keypair = getKeys(response, file.name)
        if not keypair:
            assert False, "Unable to fetch apikey and secret key"
        (apikey, secretkey) = keypair
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    sudo('cloudmonkey set color false')
    sudo('sed -i "/host/c\host=%s" ~/.cloudmonkey/config' %orchestrator_ip)
    sudo('sed -i "s/secretkey\s*\=.*$/secretkey \= %s/" ~/.cloudmonkey/config' %secretkey)
    sudo('sed -i "s/apikey\s*\=.*$/apikey \= %s/" ~/.cloudmonkey/config' %apikey)
    sudo('cloudmonkey set color true')
    env.keysupdated = True
 
@roles('build')
@task
def install_cloudstack(pkg):
    pkg_name = os.path.basename(pkg)
    temp_dir = tempfile.mkdtemp()
    host = env.roledefs['orchestrator'][0]
    with settings(host_string = host):
        sudo('mkdir -p %s' % temp_dir)
        put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
        sudo('cd %s && tar xvjf %s && sh ./cloudstack_setup.sh' %(temp_dir, pkg_name))
    execute(install_cloudstack_packages)

@roles('build')
@task
def install_contrail(pkg):
    pkg_name = os.path.basename(pkg)
    temp_dir = tempfile.mkdtemp()
    host = env.roledefs['cfgm'][0]
    with settings(host_string = host):
        sudo('mkdir -p %s' % temp_dir)
        put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
        sudo('cd %s && tar xvjf %s && sh ./contrail_setup.sh' %(temp_dir, pkg_name))
    execute(install_contrail_packages)

@roles('build')
@task
def install_xenserver(pkg):
    pkg_name = os.path.basename(pkg)
    temp_dir = tempfile.mkdtemp()
    hosts = env.roledefs['compute']
    for host in hosts:
        with settings(host_string = host):
            sudo('mkdir -p %s' % temp_dir)
            put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
            sudo('cd %s && tar xvjf %s && sh ./xen_setup.sh'%(temp_dir, pkg_name))

@roles('build')
@task
def install_packages():
    execute(install_cloudstack_packages)
    execute(install_contrail_packages)

@roles('orchestrator')
@task
def install_cloudstack_packages(pkg=None):
    if pkg:
        pkg_name = os.path.basename(pkg)
        temp_dir = tempfile.mkdtemp()
        host = env.roledefs['cfgm'][0]
        sudo('mkdir -p %s' % temp_dir)
        put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
        sudo('cd %s && tar xvjf %s && sh ./cloudstack_setup.sh' %(temp_dir, pkg_name))

    sudo('yum install --disablerepo=* --enablerepo=contrail* -y contrail-cloudstack-utils')
    check_cs_version_in_config()
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    if not 'systemvm_template' in env:
        env.systemvm_template = "http://10.84.5.120/cs-shared/cloudstack/vm_templates/systemvm64template-unknown-xen.vhd.bz2"
    sudo('sh /opt/contrail/cloudstack-utils/cloudstack-install.sh %s %s %s %s' %
                (env.config['nfs_share_path'], env.systemvm_template, env.host, env.cs_version))
    execute(cloudstack_api_setup)

@roles('cfgm')
@task
def install_contrail_packages(pkg=None):
    if pkg:
        pkg_name = os.path.basename(pkg)
        temp_dir = tempfile.mkdtemp()
        host = env.roledefs['cfgm'][0]
        sudo('mkdir -p %s' % temp_dir)
        put(pkg, '%s/%s' % (temp_dir, pkg_name), use_sudo=True)
        sudo('cd %s && tar xvjf %s && sh ./contrail_setup.sh' %(temp_dir, pkg_name))

    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    control_ip = host_string_to_ip(env.roledefs['control'][0])
    sudo('yum install --disablerepo=* --enablerepo=contrail* -y contrail-cloudstack-utils')
    sudo('sh /opt/contrail/cloudstack-utils/contrail-install.sh 127.0.0.1')

    # analytics venv installation
    with cd("/opt/contrail/analytics-venv/archive"):
        sudo("source ../bin/activate && pip install *")

    # api venv installation
    with cd("/opt/contrail/api-venv/archive"):
        sudo("source ../bin/activate && pip install *")

    # control venv installation
    sudo("echo 'HOSTIP=%s\n'>> /etc/contrail/control_param" %(control_ip))
    sudo("/bin/cp /opt/contrail/api-venv/archive/xml* /opt/contrail/control-venv/archive/")
    with cd("/opt/contrail/control-venv/archive"):
        sudo("source ../bin/activate && pip install *")
    sudo('python /opt/contrail/cloudstack-utils/contrail_post_install.py %s %s' %(orchestrator_ip, cfgm_ip))
    hosts = env.roledefs['compute']
    for host in hosts:
         compute_ip = host_string_to_ip(host)
         try:
             compute_hostname = get_hostname(compute_ip)
         except:
             print "Could not get hostname, using ipaddr"
             compute_hostname = compute_ip
         prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                        "--admin_user %s --admin_password %s --admin_tenant_name %s" \
                        %(compute_hostname, compute_ip, cfgm_ip, "admin", "password", "admin")
         sudo("python /opt/contrail/utils/provision_vrouter.py %s" %(prov_args))

@roles('cfgm')
@task
def setup_cloud():
    if 'cs_flavor' in env:
        if (env.cs_flavor != "juniper" and env.cs_flavor != "apache"):
	    print "Un supported CS flavor:%s. Exiting!!" %env.cs_flavor
            return
        print "found cs_flavor and using it\n"
    else:
        print "cs_flavor does not exist, defaulting to juniper\n"
        env.cs_flavor = "juniper"
    check_cs_version_in_config()
    orchestrator = env.roledefs['orchestrator'][0]

    # Create config file on remote host
    with tempfile.NamedTemporaryFile() as f:
        cfg = render_controller_config(env.config)
        json.dump(cfg, f)
        f.flush()
        put(f.name, '~/config.json', use_sudo=True)
    sudo('python /opt/contrail/cloudstack-utils/system-setup.py ~/config.json ' +
            '~/system-setup.log %s %s' %(env.cs_version, env.cs_flavor))
    with settings(host_string = orchestrator):
        sudo('/etc/init.d/cloudstack-management restart')
        wait_for_cloudstack_management_up(host_string_to_ip(orchestrator), env.config['cloud']['username'],
                                      env.config['cloud']['password'])

@roles('orchestrator')
@task
def cloudstack_api_setup():
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    if (orchestrator_ip == cfgm_ip):
        cfgm_ip = '127.0.0.1'
    sudo('cat <<EOF > /usr/share/cloudstack-management/webapps/client/WEB-INF/classes/contrail.properties '+ 
            '\napi.hostname=%s\napi.port=8082\nEOF' %cfgm_ip) 
    sudo('/etc/init.d/cloudstack-management restart')
    wait_for_cloudstack_management_up(env.host, env.config['cloud']['username'],
                                      env.config['cloud']['password'])

def get_ip_from_url(url):
    match = re.search(r'(http[s]?://|ftp://)(.*?)/', url)
    if match:
       try:
           return (socket.gethostbyname(match.group(2)))
       except:
           return None 
    return None

@roles('cfgm')
@task
def install_vm_template(url, name, osname):
    orchestrator = env.roledefs['orchestrator'][0]
    updateCloudMonkeyConfig()
    template_server_ip = get_ip_from_url(url)
    assert template_server_ip, "Unable to get the ip from URL. URL should have http[s] or ftp prefix"
    sudo('cloudmonkey api updateConfiguration name=secstorage.allowed.internal.sites value=%s/32' %template_server_ip)
    with settings(host_string = orchestrator):
        sudo('/etc/init.d/cloudstack-management restart')
        wait_for_cloudstack_management_up(host_string_to_ip(orchestrator), env.config['cloud']['username'],
                                      env.config['cloud']['password'])

    list_os_type = "\'list ostypes description=\"%s\"\'"%(osname)
    sudo('cloudmonkey set color false')
    output = sudo('cloudmonkey %s' %list_os_type)
    match = re.search('^id\s*=\s*(\S+)', output, re.M)
    if not match:
        output = sudo('cloudmonkey list ostypes | grep description')
        assert False, "OS name %s is not found in list types. Available options are %s" %(
                                       osname, output)
    ostype_id = match.group(1)
    register_template_opts = "name='%s' displaytext='%s' url=%s ostypeid=%s "%(name, name, url, ostype_id)+\
                             "hypervisor=XenServer format=VHD zoneid=-1 isextractable=True ispublic=True"
    sudo('cloudmonkey "register template %s"' %register_template_opts)
    interval = 30
    for retry in range (30):
        output = sudo('cloudmonkey "list templates templatefilter=all name=\'%s\'"'%name)
        state = re.search(r'isready = True', output, re.M|re.I)
        if not state:
            if (retry < 29):
                print "Template \'%s\' is not ready yet. Sleeping for %d secs before retry" %(name,interval)
                sleep(interval)
        else:
            print "Template \'%s\' is installed" %name
            break
    sudo('cloudmonkey set color true')
    if retry == 29:
        assert False, "SystemVms are not up even after %d secs" %((retry+1)*interval)

@roles('cfgm')
@task
def provision_routing():
    cfgm_ip = host_string_to_ip(env.roledefs['cfgm'][0])
    sudo('python /opt/contrail/cloudstack-utils/provision_routing.py ' +
        '%s 127.0.0.1 %s %s' % (cfgm_ip, env.config['route_target'], env.config['mx_ip']))

@roles('orchestrator')
@task
def provision_all():
    execute(setup_cloud)
    execute(provision_routing)
    execute(check_systemvms)
    execute(enable_proxyvm_console_access)
    execute(setup_vmtemplate)

@roles('compute')
@task
def enable_proxyvm_console_access():
    orchestrator_ip = host_string_to_ip(env.roledefs['orchestrator'][0])
    sudo('cd /opt/contrail/xenserver-scripts/ && sh ./xen-console-proxy-vm-setup.sh %s' %orchestrator_ip)

@roles('cfgm')
@task
def check_systemvms():
    updateCloudMonkeyConfig()
    #Increase the storage disable threshold to 97%.
    sudo('cloudmonkey update configuration name=pool.storage.capacity.disablethreshold value=0.97')

    sudo('cloudmonkey set color false')
    interval = 30
    for retry in range (30):
        output = sudo('cloudmonkey listSystemVms')
        state = re.findall(r'state = Running', output, re.M|re.I)
        if state and len(state) == 2:
            print "Both the System Vms are up and running"
            break
        else:
            if (retry < 29):
                print "System VMs are not up. Sleeping for %d secs before retry" %interval
                sleep(interval)
    sudo('cloudmonkey set color true')
    if retry == 29:
        assert False, "SystemVms are not up even after %d secs" %((retry+1)*interval)

@roles('orchestrator')
@task
def setup_vmtemplate():
    execute(install_vm_template, env.config['vm_template_url'],
            env.config['vm_template_name'], 'CentOS 5.6 (32-bit)')
    execute(install_vm_template, env.config['vsrx_template_url'],
            env.config['vsrx_template_name'], 'Other (32-bit)')

@roles('build')
@task
def run_sanity(feature='sanity', test=None):
    repo = env.test_repo_dir
    env_vars = "PARAMS_FILE=sanity_params.ini PYTHONPATH='../fixtures'"
    suites = {
              'basic_vn_vm'  : ['%s/scripts/vm_vn_tests.py' % repo],
              'vpc'          : ['%s/scripts/vpc/sanity.py' % repo],
              }

    env_vars = "PARAMS_FILE=sanity_params.ini PYTHONPATH='../fixtures:.:./cloudstack:/opt/contrail/cloudstack-utils'"
    cmds = {'sanity'   : '%s python cloudstack/cs_sanity_suite.py' % (env_vars)
           }

    if (feature != 'help' and
        feature not in suites.keys() + cmds.keys()):
        print "ERROR: Unsuported feature '%s'" % feature
        feature = 'help'

    if feature == 'help':
        print "Usage: fab run_sanity[<:feature>[,list]|[,<testcase>]]"
        print "       fab run_sanity[:%s]" % ' | :'.join(suites.keys() + cmds.keys())
        print "\n<:feature> is Optional; Default's to <:sanity>"
        print "<:feature><,list> Lists the testcase in the specified <feature> as below,"
        print "\tmod1.class1.test1"
        print "\tmod1.class2.test1"
        print "\tmod2.class1.test1"
        print "\n<:feature><,testcase> Runs the specified <testcase>"
        print "\tExample:"
        print "\tfab run_sanity:feature1,mod1.class2.test1"
        return

    if feature not in cmds.keys():
        if test == 'list':
            print "\nList of tests:\n\t" + '\n\t'.join(get_testcases(suites[feature]))
            return
        elif test:
            tests = get_testcases(suites[feature])
            if test not in tests:
                print "Test '%s' not present in %s." % (test, suites[feature])
                return
        else:
            tests = [get_module(suite) for suite in suites[feature]]
            test = ' '.join(tests)

    from tasks.tester import *
    execute(setup_test_env)
    #cfgm_host = env.roledefs['cfgm'][0]
    cfgm_host = env.roledefs['cfgm'][0]
    with settings(host_string = cfgm_host):
        with cd('%s/scripts' %(get_remote_path(env.test_repo_dir))):
            if feature in cmds.keys():
                sudo(cmds[feature])
                return
            sudo(cmd + test)

#end run_sanity

import os
import re
import json
import string
import socket
import tempfile
from random import randrange
from datetime import datetime as dt

from fabfile.config import *
from fabfile.utils.host import *
from fabfile.utils.interface import *
from fabfile.utils.multitenancy import *
from fabfile.utils.fabos import detect_ostype
from fabric.contrib.files import exists

from fabfile.tasks.install import pkg_install

devstack_flag = False

def get_address_family():
    address_family = os.getenv('AF', 'dual')
    # ToDo: CI to execute 'v4' testcases alone for now
    if os.getenv('GUESTVM_IMAGE', None):
        address_family = 'v4'
    return address_family

@roles('build')
@task
def setup_test_env():
    cfgm_host = env.roledefs['cfgm'][0]
    cfgm_ip = hstr_to_ip(cfgm_host)
    with settings(warn_only=True):
        is_git_repo = local('git branch').succeeded
    if not is_git_repo:
        with settings(host_string=cfgm_host):
            build_id = sudo('cat /opt/contrail/contrail_packages/VERSION')
        fab_revision = build_id
        revision = build_id
        print "Testing from the CFGM."
    else:
        with settings(warn_only=True):
            fab_revision = local('git log --format="%H" -n 1', capture=True)
            if CONTROLLER_TYPE == 'Cloudstack':
                revision = local('cat %s/.git/refs/heads/cs_sanity' % env.test_repo_dir, capture=True)
            else:
                with lcd(env.test_repo_dir):
                    revision = local('git log --format="%H" -n 1', capture=True)

    if not env.roledefs['build'][0] == cfgm_host:
        execute(copy_dir, env.test_repo_dir, cfgm_host)

    sanity_testbed_dict = {
        'hosts': [],
        'vgw': [],
        'hosts_ipmi': []
    }

    sample_ini_file = env.test_repo_dir + '/' + 'sanity_params.ini.sample'
    with open(sample_ini_file, 'r') as fd_sample_ini:
        contents_sample_ini = fd_sample_ini.read()
    sanity_ini_templ = string.Template(contents_sample_ini)

    if CONTROLLER_TYPE == 'Openstack':
        with settings(host_string = env.roledefs['openstack'][0]):
            openstack_host_name = sudo("hostname")
    elif CONTROLLER_TYPE == 'Cloudstack':
        openstack_host_name = None

    with settings(host_string = env.roledefs['cfgm'][0]):
        cfgm_host_name = sudo("hostname")

    control_host_names = []
    for control_host in env.roledefs['control']:
        with settings(host_string = control_host):
            host_name = sudo("hostname")
            control_host_names.append(host_name)

    cassandra_host_names = []
    if 'database' in env.roledefs.keys():
        for cassandra_host in env.roledefs['database']:
            with settings(host_string = cassandra_host):
                host_name = sudo("hostname")
                cassandra_host_names.append(host_name)

    internal_vip = get_openstack_internal_vip()
    for host_string in env.roledefs['all']:
        host_ip = host_string.split('@')[1]
        with settings(host_string = host_string):
            host_name = sudo("hostname")

        host_dict = {}
        # We may have to change it when we have HA support in Cloudstack
        host_dict['ip'] = "127.0.0.1" if (CONTROLLER_TYPE == 'Cloudstack' and host_string in env.roledefs['control']) else host_ip
        host_dict['data-ip']= get_data_ip(host_string)[0]
        if host_dict['data-ip'] == host_string.split('@')[1]:
            host_dict['data-ip'] = get_data_ip(host_string)[0]
        host_dict['control-ip']= get_control_host_string(host_string).split('@')[1]
       
        host_dict['name'] = host_name
        host_dict['username'] = host_string.split('@')[0]
        host_dict['password'] =get_env_passwords(host_string)
        host_dict['roles'] = []
  
        if not internal_vip:
            if CONTROLLER_TYPE == 'Openstack' and host_string in env.roledefs['openstack']:
                role_dict = {'type': 'openstack', 'params': {'cfgm': cfgm_host_name}}
                host_dict['roles'].append(role_dict)
            elif CONTROLLER_TYPE == 'Cloudstack' and host_string in env.roledefs['orchestrator']:
                role_dict = {'type': 'orchestrator', 'params': {'cfgm': cfgm_host_name}}
                host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['cfgm']:
            role_dict = {'type': 'cfgm', 'params': {'collector': host_name, 'cassandra': ' '.join(cassandra_host_names)}}
            if CONTROLLER_TYPE == 'Openstack':
                if internal_vip:
                    role_dict['openstack'] = 'contrail-vip' 
                else:
                    role_dict['openstack'] = openstack_host_name
            host_dict['roles'].append(role_dict)
            # Currently Cloudstack supports all-in-one model alone for contrail hence piggybacking Controller role on to cfgm
            if CONTROLLER_TYPE == 'Cloudstack':
                role_dict = { 'type': 'collector', 'params': {'cassandra': ' '.join(cassandra_host_names)} }
                host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['control']:
            role_dict = {'type': 'bgp', 'params': {'collector': cfgm_host_name, 'cfgm': cfgm_host_name}}
            host_dict['roles'].append(role_dict)

        if 'database' in env.roledefs.keys() and host_string in env.roledefs['database']:
            role_dict = { 'type': 'database', 'params': {'cassandra': ' '.join(cassandra_host_names)} }
            host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['compute']:
            role_dict = {'type': 'compute', 'params': {'collector': cfgm_host_name, 'cfgm': cfgm_host_name}}
            role_dict['params']['bgp'] = []
            if len(env.roledefs['control']) == 1:
                role_dict['params']['bgp'] = control_host_names
            else:
                for control_node in control_host_names:
                    role_dict['params']['bgp'].append(control_node)
               # role_dict['params']['bgp'].extend(control_host_names[randrange(len(env.roledefs['control']))])
            host_dict['roles'].append(role_dict)

        if 'collector' in env.roledefs.keys() and host_string in env.roledefs['collector']:
            role_dict = { 'type': 'collector', 'params': {'cassandra': ' '.join(cassandra_host_names)} }
            host_dict['roles'].append(role_dict)

        if 'webui' in env.roledefs.keys() and host_string in env.roledefs['webui']:
            role_dict = { 'type': 'webui', 'params': {'cfgm': cfgm_host_name} }
            host_dict['roles'].append(role_dict)

        sanity_testbed_dict['hosts'].append(host_dict)
        if env.has_key('vgw'): sanity_testbed_dict['vgw'].append(env.vgw)

    # Adding vip VIP dict for HA test setup
    if CONTROLLER_TYPE == 'Openstack':
        with settings(host_string = env.roledefs['openstack'][0]):
            if internal_vip:
                host_dict = {}
    # We may have to change it when we have HA support in Cloudstack
                host_dict['data-ip']= get_keystone_ip()
                host_dict['control-ip']= get_keystone_ip()
                host_dict['ip']= get_keystone_ip()
                host_dict['name'] = 'contrail-vip'     
                with settings(host_string = env.roledefs['cfgm'][0]):
                    host_dict['username'] = host_string.split('@')[0]
                    host_dict['password'] = get_env_passwords(host_string)
                host_dict['roles'] = []
                role_dict = {'type': 'openstack', 'params': {'cfgm': cfgm_host_name}}
                host_dict['roles'].append(role_dict)
                sanity_testbed_dict['hosts'].append(host_dict)
    # get host ipmi list
    if env.has_key('hosts_ipmi'):
        sanity_testbed_dict['hosts_ipmi'].append(env.hosts_ipmi)

    # for every host_string
    with settings(host_string = cfgm_host):
        repo_dir_name = env.test_repo_dir.split('/')[-1]
        repo_path= get_remote_path(env.test_repo_dir)

        # generate json file and copy to cfgm
        sanity_testbed_json = json.dumps(sanity_testbed_dict)

        stop_on_fail = env.get('stop_on_fail', False)
        mail_to = env.get('mail_to', '')
        log_scenario = env.get('log_scenario', 'Sanity')
        if CONTROLLER_TYPE == 'Cloudstack': 
            stack_password= 'password'
            stack_tenant= 'default-project'
            stack_user= 'admin'
        else:
            stack_user= get_keystone_admin_user()
            stack_password = get_keystone_admin_password()
            stack_tenant = get_keystone_admin_tenant_name()
        # Few hardcoded variables for sanity environment 
        # can be removed once we move to python3 and configparser
        stack_domain = 'default-domain'
        webserver_host = '10.204.216.50'
        webserver_user = 'bhushana'
        webserver_password = 'bhu@123'
        webserver_log_path = '/home/bhushana/Documents/technical/logs/'
        webserver_report_path = '/home/bhushana/Documents/technical/sanity'
        webroot = 'Docs/logs'
        mail_server = '10.204.216.49'
        mail_port = '25'
        fip_pool_name = 'floating-ip-pool'
        public_virtual_network='public'
        public_tenant_name='admin'
        fixture_cleanup = 'yes'
        generate_html_report = 'True'
        key = 'key1'
        mailSender = 'contrailbuild@juniper.net'

        router_asn = getattr(testbed, 'router_asn', '')
        public_vn_rtgt = getattr(testbed, 'public_vn_rtgt', '')
        public_vn_subnet = getattr(testbed, 'public_vn_subnet', '')
        ext_routers = getattr(testbed, 'ext_routers', '')
        router_info = str(ext_routers)
        test_verify_on_setup = getattr(env, 'test_verify_on_setup', True)
        webui = getattr(testbed, 'webui', False)
        horizon = getattr(testbed, 'horizon', False)
        ui_config = getattr(testbed, 'ui_config', False)
        ui_browser = getattr(testbed, 'ui_browser', False)
        if 'mail_server' in env.keys():
            mail_server = env.mail_server
            mail_port = env.mail_port

        sanity_params = sanity_ini_templ.safe_substitute(
            {'__testbed_json_file__'   : 'sanity_testbed.json',
             '__nova_keypair_name__'   : key,
             '__stack_user__'          : stack_user,
             '__stack_password__'      : stack_password,
             '__stack_tenant__'        : stack_tenant,
             '__stack_domain__'        : stack_domain,
             '__keystone_ip__'         : get_keystone_ip(),
             '__multi_tenancy__'       : get_mt_enable(),
             '__address_family__'      : get_address_family(),
             '__log_scenario__'        : log_scenario,
             '__generate_html_report__': generate_html_report,
             '__fixture_cleanup__'     : fixture_cleanup,
             '__webserver__'           : webserver_host,
             '__webserver_user__'      : webserver_user,
             '__webserver_password__'  : webserver_password,
             '__webserver_log_dir__'   : webserver_log_path,
             '__webserver_report_dir__': webserver_report_path,
             '__webroot__'             : webroot,
             '__mail_server__'         : mail_server,
             '__mail_port__'           : mail_port,
             '__sender_mail_id__'      : mailSender,
             '__receiver_mail_id__'    : mail_to,
             '__http_proxy__'          : env.get('http_proxy', ''),
             '__ui_browser__'          : ui_browser,
             '__ui_config__'           : ui_config,
             '__horizon__'             : horizon,
             '__webui__'               : webui,
             '__devstack__'            : devstack_flag,
             '__public_vn_rtgt__'      : public_vn_rtgt,
             '__router_asn__'          : router_asn,
             '__router_name_ip_tuples__': router_info,
             '__public_vn_name__'      : fip_pool_name,
             '__public_virtual_network__':public_virtual_network,
             '__public_tenant_name__'  :public_tenant_name,
             '__public_vn_subnet__'    : public_vn_subnet,
             '__test_revision__'       : revision,
             '__fab_revision__'        : fab_revision,
             '__test_verify_on_setup__': test_verify_on_setup,
             '__stop_on_fail__'        : stop_on_fail,
             '__ha_setup__'            : getattr(testbed, 'ha_setup', ''),
             '__ipmi_username__'       : getattr(testbed, 'ipmi_username', ''),
             '__ipmi_password__'       : getattr(testbed, 'ipmi_password', '')
            })

        fd, fname = tempfile.mkstemp()
        of = os.fdopen(fd, 'w')
        of.write(sanity_testbed_json)
        of.close()
        put(fname, "%s/sanity_testbed.json" %(repo_path), use_sudo=True)
        local ("cp %s %s/sanity_testbed.json" %(fname, env.test_repo_dir))
        os.remove(fname)

        fd, fname = tempfile.mkstemp()
        of = os.fdopen(fd, 'w')
        of.write(sanity_params)
        of.close()
        put(fname, "%s/sanity_params.ini" %(repo_path), use_sudo=True)
        local ("cp %s %s/sanity_params.ini" %(fname, env.test_repo_dir))
        os.remove(fname)
        pkg = ""
        if CONTROLLER_TYPE == 'Cloudstack':
            with settings(warn_only = True):
                sudo('python-pip install fixtures testtools fabric')
        else:
            with settings(warn_only = True):
                run('rm -rf /tmp/pip-build-root')
                if detect_ostype() in ['centos', 'redhat']:
                    pkg = 'fixtures testtools testresources discover \
                        testrepository junitxml pytun'
                elif 'ubuntu' == detect_ostype():
                    pkg = 'fixtures testtools testresources \
                           testrepository junitxml pytun'
                if os.environ.has_key('GUESTVM_IMAGE'):
                    pkg = pkg + ' pexpect'
                if ui_browser:
                    pkg = pkg + ' pyvirtualdisplay selenium'
                if exists('/opt/contrail/api-venv/bin/activate'):
                    sudo('source /opt/contrail/api-venv/bin/activate && \
                        pip install --upgrade unittest2 && \
                        pip install --upgrade %s' %pkg)
                else:
                    # Avoid installing linecache2 as dependency on unittest2
                    # Avoid "TypeError: dist must be a Distribution instance"
                    sudo("pip install linecache2")

                    sudo("pip install --upgrade unittest2")
                    sudo("pip install --upgrade %s" %pkg)
                if not exists('/usr/bin/ant'):
                    pkg_install(['ant'],disablerepo = False)
                    ant_version = sudo('ant -version')
                    if ('1.7' in ant_version):
                        pkg_install(['ant-junit' , 'ant-trax'] , disablerepo = False)
                    if ('1.9' in ant_version):
                        pkg_install(['ant-junit'] , disablerepo = False)

                pkg_install(['patch', 'python-heatclient'],disablerepo = False)

        for host_string in env.roledefs['compute']:
            with settings(host_string=host_string):
                if 'centos' == detect_ostype():
                    sudo("yum -y --disablerepo=* --enablerepo=contrail* install tcpdump")
                if 'redhat' == detect_ostype():
                    sudo("yum -y install tcpdump")
#end setup_test_env

def get_remote_path(path):
    user_home = os.path.expanduser('~')
    remote_dir = "~/%s" % path.replace(user_home,'')
    return remote_dir

def get_test_features(feature=None):
    cmd = "python contrail-test list"
    if feature:
        cmd += " -f %s" % feature
    cfgm_host = env.roledefs['cfgm'][0]
    with settings(hide('everything'), host_string=cfgm_host):
        remote_test_dir = get_remote_path(env.test_repo_dir)
        if not exists(remote_test_dir):
            print "Setting up test enviroinment in the first cfgm..."
            print "Will take maximum of 2 minutes"
            execute(setup_test_env)
        with cd('%s/tools/' % remote_test_dir):
            features = sudo(cmd)
    return features.split("\r\n")

@roles('build')
@task
def run_sanity(feature='sanity', test=None):
    repo = env.test_repo_dir
    test_delay_factor = os.environ.get("TEST_DELAY_FACTOR") or "1.0"
    test_retry_factor = os.environ.get("TEST_RETRY_FACTOR") or "1.0"

    date_string = dt.now().strftime('%Y-%m-%d_%H:%M:%S')
    env_vars = " TEST_DELAY_FACTOR=%s TEST_RETRY_FACTOR=%s SCRIPT_TS=%s " % (
        test_delay_factor, test_retry_factor, date_string)

    if os.environ.has_key('GUESTVM_IMAGE'):
        env_vars = env_vars + ' ci_image=%s' %(os.environ['GUESTVM_IMAGE'])
    elif env.has_key('guestvm_image'):
        env_vars = env_vars + ' ci_image=%s' % env.get('guestvm_image')

    if feature in ('upgrade','upgrade_only'):
        with settings(host_string = env.roledefs['cfgm'][0]):
                put("./fabfile/testbeds/testbed.py", "/opt/contrail/utils/fabfile/testbeds/testbed.py", use_sudo=True)
                if not files.exists("/tmp/temp/%s" % os.path.basename(test)):
                    sudo("mkdir /tmp/temp")
                    put(test,"/tmp/temp/", use_sudo=True)
        env_vars = "PARAMS_FILE=sanity_params.ini PYTHONPATH='../scripts:../fixtures'"

    cmds = {'sanity'       : './run_tests.sh --sanity --send-mail -U',
            'quick_sanity' : './run_tests.sh -T quick_sanity --send-mail -t',
            'ci_sanity'    : './run_tests.sh -T ci_sanity --send-mail -U',
            'ci_sanity_WIP': './run_tests.sh -T ci_sanity_WIP --send-mail -U',
            'ci_svc_sanity': 'python ci_svc_sanity_suite.py',
            'regression'   : 'python regression_tests.py',
            'upgrade'      : './run_tests.sh -T upgrade --send-mail -U',
            'webui_sanity' : 'python webui_tests_suite.py',
            'ci_webui_sanity' : 'python ci_webui_sanity.py',
            'devstack_sanity' : 'python devstack_sanity_tests_with_setup.py',
            'upgrade_only' : 'python upgrade/upgrade_only.py'
             }
    if CONTROLLER_TYPE == 'Cloudstack':
        env_vars = "PARAMS_FILE=sanity_params.ini PYTHONPATH='../fixtures:.:./cloudstack:/opt/contrail/cloudstack' TEST_DELAY_FACTOR=%s TEST_RETRY_FACTOR=%s" % (test_delay_factor, test_retry_factor)
        cmds = {'sanity'   : 'python cloudstack/cs_sanity_suite.py'
               }

    if feature != 'help':
        if feature not in get_test_features() + cmds.keys():
            print "ERROR: Unsuported feature '%s'" % feature
            feature = 'help'

    if feature == 'help':
        print "Usage: fab run_sanity[<:feature>[,list]|[,<testcase>]]"
        print "       fab run_sanity[:%s]" % ' | :'.join(get_test_features() + cmds.keys())
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
        tests = get_test_features(feature)
        if test == 'list':
            print "\nList of tests:\n\t" + '\n\t'.join(tests)
            return
        elif test:
            if any(test in a_test for a_test in tests):
                pass
            else:
                print "Test '%s' not present." % test
                return
        else:
            test = ' '.join(tests)

    execute(setup_test_env)
    cfgm_host = env.roledefs['cfgm'][0]
    with settings(host_string = cfgm_host):
        if feature in cmds.keys():
            with cd('%s/' %(get_remote_path(env.test_repo_dir))):
                cmd = '%s %s' % (env_vars, cmds[feature])
                sudo(cmd)
        else:
            with cd('%s/tools/' %(get_remote_path(env.test_repo_dir))):
                cmd = '%s python contrail-test run -T ' % (env_vars)
                sudo(cmd + test)

#end run_sanity

@roles('build')
@task
def export_testbed_details(filename='testbed_vars'):
    '''
    Export testbed details to a file

    At this moment, it is targeted so that contrail-tools can 
    retrieve its required testbed details
    '''
    # TODO 
    # Need to be able to export entire testbed details if need be
    keystone_ip = get_keystone_ip()
    keystone_admin_user = get_keystone_admin_user()
    keystone_admin_password = get_keystone_admin_password()
    admin_tenant = get_keystone_admin_tenant_name()
    api_server_host_string = testbed.env.roledefs['cfgm'][0]
    api_server_host_ip = testbed.env.roledefs['cfgm'][0].split('@')[1]
    api_server_host_user = testbed.env.roledefs['cfgm'][0].split('@')[0]
    api_server_host_password = get_env_passwords(api_server_host_string)
    public_network_rt = getattr(testbed, 'public_vn_rtgt', None)
    public_network_subnet = getattr(testbed, 'public_vn_subnet', None)
    router_asn = getattr(testbed, 'router_asn', '64512')
    mx_gw_test = False
    if 'MX_GW_TEST' in os.environ.keys():
        mx_gw_test = os.environ['MX_GW_TEST']
    mx_gw_test = int(getattr(env, 'mx_gw_test', mx_gw_test))

    testbed_location = getattr(env, 'testbed_location', None)
    image_web_server = getattr(env, 'image_web_server', None)
    fh = open(filename,'w')
    fh.write('export KEYSTONE_SERVICE_HOST=%s\n' % (keystone_ip))
    fh.write('export API_SERVER_IP=%s\n' % (api_server_host_ip))
    fh.write('export API_SERVER_HOST_STRING=%s\n' % (api_server_host_string))
    fh.write('export API_SERVER_HOST_PASSWORD=%s\n' % (api_server_host_password))
    fh.write('export PUBLIC_NETWORK_SUBNET=%s\n' % (public_network_subnet))
    fh.write('export PUBLIC_NETWORK_RT=%s\n' % (public_network_rt))
    fh.write('export ROUTER_ASN=%s\n' % (router_asn))
    fh.write('export NODEHOME=~%s\n' % (api_server_host_user))
    fh.write('export MX_GW_TEST=%s\n' % (mx_gw_test))
    if mx_gw_test:
        fh.write('export PUBLIC_ACCESS_AVAILABLE=%s\n' % (mx_gw_test))
    if testbed_location:
        fh.write('export TESTBED_LOCATION=%s\n' % (testbed_location))
    if image_web_server:
        fh.write('export IMAGE_WEB_SERVER=%s\n' % (image_web_server))
    fh.close()
# end export_testbed_details

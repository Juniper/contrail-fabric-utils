import os
import re
import json
import string
import socket
import tempfile
from string import whitespace
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
        'esxi_vms':[],
        'hosts_ipmi': [],
        'tor':[],
        'vcenter_servers':[],
        'sriov':[],
        'dpdk':[],
        'ns_agilio_vrouter':[],
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

    # Read ToR config
    sanity_tor_dict = {}
    if env.has_key('tor_agent'):
        sanity_testbed_dict['tor_agent'] = env.tor_agent

    # Read any tor-host config
    if env.has_key('tor_hosts'):
        sanity_testbed_dict['tor_hosts'] = env.tor_hosts

    # Read any MX config (as physical_router )
    if env.has_key('physical_routers'):
        sanity_testbed_dict['physical_routers'] = env.physical_routers

    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            host_dict = {}
            host_dict['ip'] = esxi_hosts[esxi]['ip']
            host_dict['data-ip'] = host_dict['ip']
            host_dict['control-ip'] = host_dict['ip']
            host_dict['name'] = esxi
            host_dict['username'] = esxi_hosts[esxi]['username']
            host_dict['password'] = esxi_hosts[esxi]['password']
            if 'contrail_vm' in host_dict:
                host_dict['contrail_vm'] = esxi_hosts[esxi]['contrail_vm']['host']
            host_dict['roles'] = []
            sanity_testbed_dict['hosts'].append(host_dict)
            sanity_testbed_dict['esxi_vms'].append(host_dict)
    # Adding vip VIP dict for HA test setup
    if CONTROLLER_TYPE == 'Openstack':
        with settings(host_string = env.roledefs['openstack'][0]):
            if internal_vip:
                host_dict = {}
    # We may have to change it when we have HA support in Cloudstack
                host_dict['data-ip']= get_authserver_ip()
                host_dict['control-ip']= get_authserver_ip()
                host_dict['ip']= get_authserver_ip()
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
    #get vcenter info
    if env.has_key('vcenter_servers'):
        vcenter_info = {}
        for k in env.vcenter_servers.keys():
            vcenter_info[k] = env.vcenter_servers[k]
            server = {}
            server[k] = env.vcenter_servers[k]
            sanity_testbed_dict['vcenter_servers'].append(server)
    #get sriov info
    if env.has_key('sriov'):
        sanity_testbed_dict['sriov'].append(env.sriov)

    #get dpdk info
    if env.has_key('dpdk'):
        sanity_testbed_dict['dpdk'].append(env.dpdk)

    #get ns_agilio_vrouter info
    if env.has_key('ns_agilio_vrouter'):
        sanity_testbed_dict['ns_agilio_vrouter'].append(env.ns_agilio_vrouter)

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
            admin_user= 'admin'
        else:
            admin_user, admin_password = get_authserver_credentials()
            admin_tenant = get_admin_tenant_name()
        # Few hardcoded variables for sanity environment 
        # can be removed once we move to python3 and configparser
        stack_domain = 'default-domain'
        webserver_host = os.getenv('WEBSERVER_HOST')
        webserver_user = os.getenv('WEBSERVER_USER')
        webserver_password = os.getenv('WEBSERVER_PASSWORD')
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

        use_devicemanager_for_md5 = getattr(testbed, 'use_devicemanager_for_md5', False)
        orch = getattr(env, 'orchestrator', 'openstack')
        router_asn = getattr(testbed, 'router_asn', '')
        public_vn_rtgt = getattr(testbed, 'public_vn_rtgt', '')
        public_vn_subnet = getattr(testbed, 'public_vn_subnet', '')
        ext_routers = getattr(testbed, 'ext_routers', '')
        router_info = str(ext_routers)
        test_verify_on_setup = getattr(env, 'test_verify_on_setup', True)

        if not getattr(env, 'test', None):
            env.test={}
        stack_user = env.test.get('stack_user', None)
        stack_password = env.test.get('stack_password', None)
        stack_tenant = env.test.get('stack_tenant', None)
        tenant_isolation = env.test.get('tenant_isolation', None)

        webui = getattr(testbed, 'webui', False)
        horizon = getattr(testbed, 'horizon', False)
        ui_config = getattr(testbed, 'ui_config', False)
        ui_browser = getattr(testbed, 'ui_browser', False)
        if 'mail_server' in env.keys():
            mail_server = env.mail_server
            mail_port = env.mail_port

        vcenter_dc = ''
        if orch in ['vcenter','vcenter_gateway']:
            public_tenant_name='vCenter'

        if env.has_key('vcenter_servers'):
            if env.vcenter_servers:
                for k in env.vcenter_servers: 
                    vcenter_dc = env.vcenter_servers[k]['datacenter']

        sanity_params = sanity_ini_templ.safe_substitute(
            {'__testbed_json_file__'   : 'sanity_testbed.json',
             '__nova_keypair_name__'   : key,
             '__orch__'                : orch,
             '__admin_user__'          : admin_user,
             '__admin_password__'      : admin_password,
             '__auth_ip__'             : get_authserver_ip(),
             '__auth_port__'           : get_authserver_port(),
             '__admin_tenant__'        : admin_tenant,
             '__stack_domain__'        : stack_domain,
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
             '__ipmi_password__'       : getattr(testbed, 'ipmi_password', ''),
             '__vcenter_dc__'          : vcenter_dc,
             '__vcenter_server__'      : get_vcenter_ip(),
             '__vcenter_port__'        : get_vcenter_port(),
             '__vcenter_username__'    : get_vcenter_username(),
             '__vcenter_password__'    : get_vcenter_password(),
             '__vcenter_datacenter__'  : get_vcenter_datacenter(),
             '__vcenter_compute__'     : get_vcenter_compute(),
             '__use_devicemanager_for_md5__'       : use_devicemanager_for_md5,
             '__stack_user__'          : stack_user,
             '__stack_password__'      : stack_password,
             '__stack_tenant__'        : stack_tenant,
             '__tenant_isolation__'    : tenant_isolation,
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
                if detect_ostype() in ['centos', 'redhat', 'centoslinux']:
                    sudo('yum -y install python-pip')
                    pkg = 'fixtures==1.0.0 testtools==1.7.1 testresources==0.2.7 discover \
                        testrepository junitxml pytun requests==2.3.0 pyvmomi==5.5.0 eventlet \
                        tabulate'
                elif 'ubuntu' == detect_ostype():
                    pkg = 'fixtures==1.0.0 testtools==1.7.1 testresources==0.2.7 \
                           testrepository junitxml pytun pyvmomi==5.5.0 eventlet tabulate '
                    output = sudo('pip show requests | grep Version')
                    if output.succeeded:
                        version = output.split(':')[1].translate(None, whitespace)
                        if version <= 2.3:
                            if (LooseVersion(version) < LooseVersion('2.3.0')):
                                pkg += ' requests==2.3.0'
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
                    sudo ("pip install --upgrade easyprocess")
                if not exists('/usr/bin/ant'):
                    pkg_install(['ant'],disablerepo = False)
                    ant_version = sudo('ant -version')
                    if ('1.7' in ant_version):
                        pkg_install(['ant-junit' , 'ant-trax'] , disablerepo = False)
                    if ('1.9' in ant_version):
                        pkg_install(['ant-junit'] , disablerepo = False)

                pkg_install(['patch', 'python-heatclient', 'python-ceilometerclient', 'python-setuptools'],disablerepo = False)

                # On centos, junos-eznc install requires devel pkgs of libxml2 and libxslt
                if detect_ostype() in ['redhat', 'centos', 'centoslinux']:
                    pkg_install(['libxslt-devel', 'libxml2-devel'], disablerepo=False)
                sudo ('pip install paramiko==1.17.0')
                sudo('pip install junos-eznc==1.2.2')
               
                #Restart DM. This is because of #1490860
                sudo('service contrail-device-manager restart')

        for host_string in env.roledefs['compute']:
            with settings(host_string=host_string):
                #pkg_install(['python-setuptools', 'python-pkg-resources', 'python-ncclient'],disablerepo = False)
                pkg_install(['python-setuptools', 'python-ncclient'],disablerepo = False)
                if detect_ostype() in ['centos', 'centoslinux', 'redhat']:
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
    image_web_server = os.environ.get("IMAGE_WEB_SERVER")

    date_string = dt.now().strftime('%Y-%m-%d_%H:%M:%S')
    env_vars = " TEST_DELAY_FACTOR=%s TEST_RETRY_FACTOR=%s SCRIPT_TS=%s " % (
        test_delay_factor, test_retry_factor, date_string)

    if os.environ.has_key('GUESTVM_IMAGE'):
        env_vars = env_vars + ' ci_image=%s' %(os.environ['GUESTVM_IMAGE'])

    if image_web_server:
        env_vars = env_vars + ' IMAGE_WEB_SERVER=%s ' % (image_web_server)

    if feature in ('upgrade','upgrade_only'):
        with settings(host_string = env.roledefs['cfgm'][0]):
                put("./fabfile/testbeds/testbed.py", "/opt/contrail/utils/fabfile/testbeds/testbed.py", use_sudo=True)
                if not files.exists("/tmp/temp/%s" % os.path.basename(test)):
                    sudo("mkdir /tmp/temp")
                    put(test,"/tmp/temp/", use_sudo=True)
        env_vars = env_vars + "PARAMS_FILE=sanity_params.ini PYTHONPATH='../scripts:../fixtures'"

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
    authserver_ip = ''
    orch = getattr(env, 'orchestrator', None)
    if orch != 'kubernetes':
        authserver_ip = get_authserver_ip()
    keystone_admin_user, keystone_admin_password = get_authserver_credentials()
    admin_tenant = get_admin_tenant_name()

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
    fh.write('export KEYSTONE_SERVICE_HOST=%s\n' % (authserver_ip))
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

@roles('rally')
@task
def run_rally(task_args_file=None):
    import yaml
    if task_args_file:
        if os.path.isfile(task_args_file):
            put(task_args_file, '/tmp')
            with cd('/usr/share/rally/samples/tasks/scenarios/custom'):
                run('python run_rally.py --task-args-file /tmp/' + os.path.basename(task_args_file))
        else:
            raise IOError("%s: No such file or directory" % task_args_file)
    elif testbed.rally_task_args:
        with cd('/usr/share/rally/samples/tasks/scenarios/custom'):
            run("python run_rally.py --task-args '" + yaml.dump(testbed.rally_task_args).rstrip('\n') + "'")
# end run_rally

@roles('build')
@task
def install_pkgs_on_roles(role_names, package_names, disablerepo=False):
    ''' Install ubuntu/centos packages on all nodes with specific role
    '''
    pkgs =  package_names.split(',')
    roles =  role_names.split(',')
    execute('pkg_install', pkgs, disablerepo=disablerepo, roles=roles)
# end install_pkgs_on_roles

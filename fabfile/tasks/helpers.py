import sys
import socket
import os
import time
from copy import deepcopy
import collections

from fabfile.config import *
import fabfile.common as common
from fabfile.utils.host import *
from fabfile.utils.multitenancy import *
from fabfile.utils.fabos import *
from fabric.contrib.files import exists
import datetime
from fabfile.tasks.esxi_defaults import apply_esxi_defaults

@task
@parallel
@roles('compute')
def compute_reboot(waitup='yes'):
    if env.roledefs['compute']:
        reboot_node(waitup, env.host_string)

@task
def reboot_node(waitup, *args):
    for host_string in args:
        user, hostip = host_string.split('@')
        with settings(hide('running'), host_string=host_string, warn_only=True):
            #Fabric hangs when reboot --force is issued, so adding timeout
            #as workaround.
            try:
                sudo("/etc/contrail/contrail_reboot", timeout=5)
            except CommandTimeout:
                pass

        print 'Reboot issued; Waiting for the node (%s) to go down...' % hostip
        common.wait_until_host_down(wait=300, host=hostip)
        if waitup == 'no':
            return
        print 'Node (%s) is down... Waiting for node to come back' % hostip
        sys.stdout.write('.')
        count = 0
        while not verify_sshd(hostip,
                          user,
                          env.passwords[host_string]):
            sys.stdout.write('.')
            sleep(2)
            count+=1
            if count <=1000:
                continue
            else:
                print 'Timed out waiting for node to come back up'
                sys.exit(1)
#end compute_reboot

@roles('build')
@task
def all_reimage(build_param="@LATEST"):
    for host in env.roledefs["all"]:
        for i in range(5):
            try:
                hostname = socket.gethostbyaddr( hstr_to_ip(host) )[0].split('.')[0]
            except socket.herror: 
                sleep(5)
                continue
            else:
                break

        if 'ostypes' in env.keys():
            if 'xen' in env.ostypes[host]:
                pass
            elif 'fedora' in env.ostypes[host]:
                # Fedora
                local("/cs-shared/cf/bin/reimage %s %s" %(hostname, build_param))
            elif 'ubuntu' in env.ostypes[host]:
                with settings(warn_only=True):
                    if local("/cs-shared/cf/bin/ubuntu.reimage %s" %(hostname)).failed:
                        local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s ubuntu-12.04.3" % (hostname))
            elif 'cent63' in env.ostypes[host]:
                local("/cs-shared/cf/bin/centos63.reimage %s" %(hostname))
            else:
                # CentOS
                with settings(warn_only=True):
                    if local("/cs-shared/cf/bin/centos.reimage %s %s" %(hostname, build_param)).failed:
                        local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s centos-6.4" % (hostname))
        else:
            # CentOS
            with settings(warn_only=True):
                if local("/cs-shared/cf/bin/centos.reimage %s %s" %(hostname, build_param)).failed:
                    local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s centos-6.4" % (hostname))
        sleep(5)
#end all_reimage

@roles('build')
@task
def all_sm_reimage(build_param=None):
    hosts = env.roledefs['all'][:]
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            hosts.remove(esxi_hosts[esxi]['contrail_vm']['host'])
    for host in hosts:
        hostname = None
        for i in range(5):
            try:
                hostname = socket.gethostbyaddr( hstr_to_ip(host))[0].split('.')[0]
            except socket.herror:
                sleep(5)
                continue
            else:
                break
        if not hostname:
            print "Unable to resolve %s" % (host)
            sys.exit(1)
        if build_param is not None:
            with settings(warn_only=True):
                local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s %s" % (hostname,build_param))
        else:
            if 'ostypes' in env.keys():
                if 'ubuntu' in env.ostypes[host]:
                    with settings(warn_only=True):
                        local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s ubuntu-12.04.3" % (hostname))
                else:
                    # CentOS
                    with settings(warn_only=True):
                        local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s centos-6.4" % (hostname))
            else:
                # CentOS
                with settings(warn_only=True):
                    local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s centos-6.4" % (hostname))
            sleep(1)

    if esxi_hosts:
        for esxi in esxi_hosts:
            with settings(warn_only=True):
                local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s %s" % (esxi,'esx5.5'))
                sleep(15*60)
#end all_sm_reimage

@roles('compute')
@task
def contrail_version():
    sudo("contrail-version")

@task
@parallel
@roles('all')
def all_reboot():
    with settings(hide('running'), warn_only=True):
        if env.host_string in env.roledefs['compute']:
            compute_reboot()
        else:
            #Fabric hangs when reboot --force is issued, so adding timeout as
            # workaround.
            try:
                sudo("reboot --force", timeout=5)
            except CommandTimeout:
                pass
#end all_reboot

@task
@roles('build')
def check_ssh():
    sshd_down_hosts = ''
    for host_string in env.roledefs["all"]:
        user, hostip = host_string.split('@')
        password = env.passwords[host_string]
        if not verify_sshd(hostip, user, password):
            sshd_down_hosts += "%s : %s\n" % (host_string, password)

    if sshd_down_hosts: 
        raise Exception("Following list of hosts are down: \n %s" % sshd_down_hosts)
    else:
        print "\n\tAll nodes are Up."
    
@roles('all')
@task
def all_command(command):
    sudo(command)
#end all_command

@roles('all')
@task
def all_ping():
    for host in env.hostnames["all"]:
        local("ping -c 1 -q %s " %(host))
#end all_ping

@roles('all')
@task
def all_version():
    sudo("contrail-version")
#end all_ping

@roles('all')
@task
def check_reimage_state():
    failed_host = []
    hosts = env.hostnames['all'][:]
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            if env['host_string'] == esxi_hosts[esxi]['contrail_vm']['host']:
                print "skipping contrail vm, continue..."
                return
    for host in hosts:
        if exists('/opt/contrail'):
            failed_host.append(host)
    if failed_host:
        print "reimage failed on hosts: %s, aborting..." %failed_host
        sys.exit(1)
    else:
        print "reimage successful, continue..."
#end check_reimage_state

@roles('all')
@task
def all_crash():
    sudo("ls -l /var/crashes")

@roles('control')
@task
def control_crash():
    sudo("ls -l /var/crashes")

@roles('compute')
@task
def compute_crash():
    sudo("ls -l /var/crashes")

@roles('compute')
@task
def compute_provision():
    cfgm_host = env.roledefs['cfgm'][0]
    cfgm_ip = hstr_to_ip(cfgm_host)
    tgt_ip = env.host_string.split('@')[1]
    tgt_hostname = sudo("hostname")
    prov_args = "--host_name %s --host_ip %s --api_server_ip %s --oper add " \
                                %(tgt_hostname, tgt_ip, cfgm_ip) 
    sudo("/opt/contrail/utils/provision_vrouter.py %s" %(prov_args))


@roles('compute')
@task
def install_img_agent():
    sudo("yum localinstall %s/extras/contrail-agent*.rpm" %(INSTALLER_DIR))
#end install_img_agent

#@roles('compute')
@task
def test():
    sudo('cd /; ls')

@roles('compute')
@task
def start_vnc():
    sudo("vncserver")

@roles('cfgm')
@task
def cfgm_status():
    sudo("service contrail-api status")
    sudo("service contrail-schema status")
    sudo("service contrail-discovery status")
    sudo("service contrail-svc-monitor status")
    sudo("service ifmap status")
#end cfgm_status

@roles('cfgm')
@task
def api_restart():
    sudo("service contrail-api restart")
#end api_restart

@roles('cfgm')
@task
def schema_restart():
    sudo("service contrail-schema restart")
#end schema_restart

@roles('database')
@task
def database_restart():
   sudo("service contrail-database restart")
#end database_restart

@roles('database')
@task
def database_status():
    sudo("service contrail-database status")
#end database_status

@roles('control')
@task
def control_restart():
    sudo("service contrail-control restart")
#end control_restart

@roles('control')
@task
def control_status():
    sudo("service contrail-control status")
#end control_status

@roles('compute')
@task
def compute_status():
    nova_compute = "openstack-nova-compute"
    if detect_ostype() in ['ubuntu']:
        nova_compute = "nova-compute"
    sudo("service %s status" % nova_compute)
    sudo("service contrail-vrouter-agent status")
#end compute_status

@roles('compute')
@task
def agent_restart():
    sudo("service contrail-vrouter-agent restart")
#end agent_restart

@roles('cfgm')
@task
def config_demo():
    cfgm_ip = hstr_to_ip(get_control_host_string(env.roledefs['cfgm'][0]))

    with cd(UTILS_DIR):
        sudo("python demo_cfg.py --api_server_ip %s --api_server_port 8082 --public_subnet %s %s" %(cfgm_ip, testbed.public_vn_subnet, get_mt_opts()))
        sudo("python add_route_target.py --routing_instance_name default-domain:demo:public:public --route_target_number %s --router_asn %s --api_server_ip %s --api_server_port 8082 %s" \
                    %(testbed.public_vn_rtgt, testbed.router_asn, cfgm_ip, get_mt_opts()))
        sudo("python create_floating_pool.py --public_vn_name default-domain:demo:public --floating_ip_pool_name pub_fip_pool --api_server_ip %s --api_server_port 8082 %s" %(cfgm_ip, get_mt_opts()))
        sudo("python use_floating_pool.py --project_name default-domain:demo --floating_ip_pool_name default-domain:demo:public:pub_fip_pool --api_server_ip %s --api_server_port 8082 %s" %(cfgm_ip, get_mt_opts()))

#end config_demo


@hosts(*env.roledefs['openstack'][0:1])
@task
def add_images(image=None):
    mount=None
    if '10.84' in env.host:
        mount= '10.84.5.100'
    elif '10.204' in env.host:
        mount= '10.204.216.51'
    if not mount :
        return 

    images = [ ("turnkey-redmine-12.0-squeeze-x86.vmdk", "redmine-web"),
               ("turnkey-redmine-12.0-squeeze-x86-mysql.vmdk", "redmine-db"),
               ("ubuntu.img", "ubuntu"),
               ("traffic/ubuntu-traffic.img", "ubuntu-traffic"),
               ("vsrx/junos-vsrx-12.1-in-network.img", "nat-service"),
               ("vsrx/junos-vsrx-12.1-transparent.img", "vsrx-bridge"),
               ("ubuntu-netperf.img", "ubuntu-netperf"),
               ("analyzer/analyzer-vm-console.qcow2", "analyzer"),
               ("ddos.qcow2", "ddos"),
               ("demo-ddos.vmdk", "demo-ddos"),
               ("Tier1-LB-Snapshot.qcow2", "Tier1-LB"),
               ("Tier2-Web-Snapshot.qcow2", "Tier2-Web"),
               ("Tier2-DB-Snapshot.qcow2", "Tier2-DB"),
               ("vsrx-fw-no-ping.qcow2", "vsrx-fw-no-ping"),
               ("sugarcrm.vmdk", "sugarcrm") 
             ]

    for (loc, name) in images:
        if image is not None and image != name:
            continue
        local = "/images/"+loc+".gz"
        remote = loc.split("/")[-1]
        remote_gz = remote+".gz"
        sudo("wget http://%s/%s" % (mount, local)) 
        sudo("gunzip " + remote_gz)

        if ".vmdk" in loc:
            sudo("(source /etc/contrail/openstackrc; glance image-create --name '"+name+"' --is-public True --container-format ovf --disk-format vmdk --file "+remote+")")
        else:
            sudo("(source /etc/contrail/openstackrc; glance image-create --name '"+name+"' --is-public True --container-format ovf --disk-format qcow2 --file "+remote+")")
        sudo("rm "+remote)
#end add_images

def preload_image_to_esx(url, glance_id, sizes, version):
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if not esxi_hosts:
        return
    for esxi in esxi_hosts.values():
        if esxi['contrail_vm']['host'] in env.roledefs['compute']:
            apply_esxi_defaults(esxi)
            # for havana(2013.2), images are stored under datastore/vmware_base/
            base = esxi['datastore'] + 'vmware_base/'
            # for icehouse, images are stored under datstore/<ip>_base/<glanceid>/
            if '2014.1' in version:
                ip = esxi['contrail_vm']['host'].split('@')[-1]
                base = esxi['datastore'] + ip + '_base/' + glance_id + '/'

            with settings(host_string = esxi['username'] + '@' + esxi['ip'],
                          password = esxi['password'], warn_only=True,
                          shell = '/bin/sh -l -c'):
                 run('mkdir -p %s' % base)
                 with cd(base):
                      run('wget -O ' + glance_id + '-sparse.vmdk.gz ' + url)
                      run('gunzip ' + glance_id + '-sparse.vmdk.gz')
                      run('vmkfstools -i ' + glance_id + '-sparse.vmdk -a ide ' + glance_id + '.vmdk')

                      run('rm ' + glance_id + '-sparse.vmdk')
                      for size in sizes:
                          run('vmkfstools -i ' + glance_id + '.vmdk -a ide ' + glance_id + '.' + str(size) + '.vmdk')
                          run('vmkfstools -X ' + str(size) + 'G ' + glance_id + '.' + str(size) + '.vmdk')

#end preload_images_to_esx

@hosts(*env.roledefs['openstack'][0:1])
@task
def add_basic_images(image=None):
    mount=None
    if '10.84' in env.host:
        mount= '10.84.5.100'
    elif '10.204' in env.host:
        mount= '10.204.216.51'
    if not mount :
        return

    openstack_version  = run("source /etc/contrail/openstackrc; nova-manage version")

    images = [ ("converts/ubuntu.vmdk", "ubuntu", [10,20]),
               ("converts/ubuntu-traffic.vmdk", "ubuntu-traffic", [10,20]),
               ("converts/centos-min.vmdk", "centos65-ipv6", [10]),
               ("converts/ubuntu-in-net.vmdk", "ubuntu-in-net", []),
               ("converts/ubuntu-dhcp-server.vmdk", "ubuntu-dhcp-server", []),
               ("converts/cirros-0.3.0-x86_64-disk.vmdk", "cirros", [1,10]),
               ("vsrx/junos-vsrx-12.1-transparent.img", "vsrx-bridge", []),
               ("vsrx/junos-vsrx-12.1-in-network.img", "vsrx", []),
               ("analyzer/analyzer-vm-console.qcow2", "analyzer", []),
             ]

    for (loc, name, sizes) in images:
        if image is not None and image != name:
            continue
        local = "/images/"+loc+".gz"
        remote = loc.split("/")[-1]
        remote_gz = remote+".gz"
        run("wget http://%s/%s" % (mount, local))
        run("gunzip " + remote_gz)
        if ".vmdk" in loc:
            if 'converts' in loc:
                glance_id = run("(source /etc/contrail/openstackrc; glance image-create --name '"+name+"' --is-public True --container-format bare --disk-format vmdk --property vmware_disktype='sparse' --property vmware_adaptertype='ide' < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
            else:
                glance_id = run("(source /etc/contrail/openstackrc; glance add name='"+name+"' is_public=true container_format=ovf disk_format=vmdk < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
            if glance_id.succeeded:
                preload_image_to_esx('http://%s/%s' % (mount,local), glance_id, sizes, openstack_version)
        else:
           run("(source /etc/contrail/openstackrc; glance image-create --name '"+name+"' --is-public True --container-format ovf --disk-format qcow2 --property hypervisor_type=qemu < "+remote+")")
        run("rm "+remote)

#end add_basic_images

@roles('compute')
@task
def virsh_cleanup():
    result = sudo("ls /etc/libvirt/qemu/instance*.xml | cut -d '/' -f 5 | cut -d '.' -f 1")
    for inst_name in result.split():
        if re.match('instance', inst_name):
            with settings(warn_only = True):
                sudo('virsh destroy %s' %(inst_name))
                sudo('virsh undefine %s' %(inst_name))
                sudo('rm -rf /var/lib/nova/instances/%s' %(inst_name))
         
#end virsh_cleanup 
@task
def virsh_cmd(cmd):
    result = sudo('virsh %s' %(cmd))
#end virsh_cmd

@task
def sudo_cmd(cmd):
    result = sudo(cmd)
#end sudo_cmd

@roles('cfgm')
@task
def net_list():
    cfgm_ip = hstr_to_ip(env.roledefs['cfgm'][0])

    os_opts = ''
    os_opts = os_opts + ' --os-username %s --os-password %s '\
                          %(get_keystone_admin_user(), get_keystone_admin_password())
    os_opts = os_opts + ' --os-tenant-name %s ' %(get_keystone_admin_tenant_name())
    os_opts = os_opts + ' --os-auth-url http://%s:5000/v2.0 ' %(cfgm_ip)

    sudo('quantum %s net-list' %(os_opts))
#end net_list

@roles('cfgm')
@task
def demo_fixup():
    sudo("service openstack-nova-compute restart")
    sudo("service contrail-schema restart")

@task
def copy(src, dst = '.'):
    put(src, dst, use_sudo=True)
#end copy

@roles('openstack','compute')
def cleanup_os_config():
    '''
    This has to be run from reset_config() task only
    '''
    dbs=['nova', 'mysql', 'keystone', 'glance', 'cinder']
    services =['mysqld', 'openstack-nova-novncproxy', 'rabbitmq-server', 'openstack-cinder-volume', 'openstack-cinder-scheduler', 'openstack-cinder-api', 'openstack-glance-registry', 'openstack-glance-api', 'openstack-nova-xvpvncproxy', 'openstack-nova-scheduler', 'openstack-nova-objectstore', 'openstack-nova-metadata-api', 'openstack-nova-consoleauth', 'openstack-nova-console', 'openstack-nova-compute', 'openstack-nova-cert', 'openstack-nova-api', 'openstack-keystone']
    ubuntu_services =['mysql', 'nova-novncproxy', 'rabbitmq-server', 'cinder-volume', 'cinder-scheduler', 'cinder-api', 'glance-registry', 'glance-api', 'nova-xvpvncproxy', 'nova-scheduler', 'nova-objectstore', 'nova-metadata-api', 'nova-consoleauth', 'nova-console', 'nova-compute', 'nova-cert', 'nova-api', 'contrail-vncserver', 'keystone', ]
    # Drop all dbs
    with settings(warn_only=True):
        token=sudo('cat /etc/contrail/mysql.token')
        for db in dbs:
            sudo('mysql -u root --password=%s -e \'drop database %s;\''  %(token, db))

        
        if detect_ostype() == 'ubuntu':
            services = ubuntu_services
        for service in services :
            sudo('sudo service %s stop' %(service))

        sudo('sudo rm -f /etc/contrail/mysql.token')
        sudo('sudo rm -f /etc/contrail/service.token')
        sudo('sudo rm -f /etc/contrail/keystonerc')
        
        #TODO 
        # In Ubuntu, by default glance uses sqlite
        # Until we have a clean way of clearing glance image-data in sqlite,
        # just skip removing the images on Ubuntu
        if not detect_ostype() in ['ubuntu']:
            sudo('sudo rm -f /var/lib/glance/images/*')
        
        sudo('sudo rm -rf /var/lib/nova/tmp/nova-iptables')
        sudo('sudo rm -rf /var/lib/libvirt/qemu/instance*')
        sudo('sudo rm -rf /var/log/libvirt/qemu/instance*')
        sudo('sudo rm -rf /var/lib/nova/instances/*')
        sudo('sudo rm -rf /etc/libvirt/nwfilter/nova-instance*')
        sudo('sudo rm -rf /var/log/libvirt/qemu/inst*')
        sudo('sudo rm -rf /etc/libvirt/qemu/inst*')
        sudo('sudo rm -rf /var/lib/nova/instances/_base/*')
        
        if detect_ostype() in ['ubuntu'] and env.host_string in env.roledefs['openstack']:
            sudo('mysql_install_db --user=mysql --ldata=/var/lib/mysql/')
#end cleanup_os_config

@roles('build')
@task
def config_server_reset(option=None, hosts=[]):
    
    for host_string in hosts:
        api_config_file = '/etc/contrail/supervisord_config_files/contrail-api.ini'
        disc_config_file = '/etc/contrail/supervisord_config_files/contrail-discovery.ini'
        schema_config_file = '/etc/contrail/supervisord_config_files/contrail-schema.ini'
        svc_m_config_file = '/etc/contrail/supervisord_config_files/contrail-svc-monitor.ini'
        
        with settings(host_string=host_string):
            try :
                if option == "add" :
                    sudo('sudo sed -i \'s/contrail-api --conf_file/contrail-api --reset_config --conf_file/\' %s' %(api_config_file))
                    sudo('sudo sed -i \'s/discovery-server --conf_file/discovery-server --reset_config --conf_file/\' %s' %(disc_config_file))
                    sudo('sudo sed -i \'s/contrail-schema --conf_file/contrail-schema --reset_config --conf_file/\' %s' %(schema_config_file))
                    sudo('sudo sed -i \'s/contrail-svc-monitor --conf_file/contrail-svc-monitor --reset_config --conf_file/\' %s' %(svc_m_config_file))
                elif option == 'delete' :
                    sudo('sudo sed -i \'s/contrail-api --reset_config/contrail-api/\' %s' %(api_config_file))
                    sudo('sudo sed -i \'s/discovery-server --reset_config/discovery-server/\' %s' %(disc_config_file))
                    sudo('sudo sed -i \'s/contrail-schema --reset_config/contrail-schema/\' %s' %(schema_config_file))
                    sudo('sudo sed -i \'s/contrail-svc-monitor --reset_config/contrail-svc-monitor/\' %s' %(svc_m_config_file))
            except SystemExit as e:
                print "Failure of one or more of these cmds are ok"
#end config_server_reset

@roles('compute')
@task
def start_servers(file_n="traffic_profile.py"):
    file_fabt = os.getcwd() + "/fabfile/testbeds/traffic_fabfile.py"
    file_proft = os.getcwd() + "/fabfile/testbeds/" + file_n

    with settings(warn_only=True):
        put(file_fabt, "~/fabfile.py", use_sudo=True)
        put(file_proft, "~/traffic_profile.py", use_sudo=True)

        sudo("fab setup_hosts start_servers")

@roles('compute')
@task
def start_clients():
    with settings(warn_only=True):
        sudo("fab setup_hosts start_clients")

# from build we go to each compute node, and from there fab run to each of the
# VMs to start traffic scripts
# testbeds/traffic_fabfile.py is copied to each compute node and is the fab file
# used to run traffic scripts in the VMs
# testbeds/traffic_profile.py describes the connections that are need to be made
# by the traffic scripts - testbeds/traffic_profile_sample.py gives one such example

@roles('build')
@task
def start_traffic():
    execute(start_servers)
    sleep(10)
    execute(start_clients)

@roles('build')
@task
def wait_till_all_up(attempts=90, interval=10, node=None, waitdown=True, contrail_role='all', reimaged=False):
    ''' Waits for given nodes to go down and then comeup within the given attempts.
        Defaults: attempts = 90 retries
                  interval = 10 secs
                  node     = env.roledefs['all']
    '''
    if node:
        nodes = node
    else:
        nodes = env.roledefs[contrail_role][:]
        if reimaged:
            esxi_hosts = getattr(testbed, 'esxi_hosts', None)
            if esxi_hosts:
                for esxi in esxi_hosts:
                    hstr = esxi_hosts[esxi]['username'] + '@' + esxi_hosts[esxi]['ip']
                    nodes.append(hstr)
                    env.passwords[hstr] = esxi_hosts[esxi]['password']
                    nodes.remove(esxi_hosts[esxi]['contrail_vm']['host'])

    nodes = [nodes] if type(nodes) is str else nodes
    #Waits for node to shutdown
    if waitdown != 'False' and not (reimaged and esxi_hosts):
        for node in nodes:
            nodeip = node.split('@')[1]
            print 'Waiting for the node (%s) to go down...' %nodeip
            common.wait_until_host_down(host=nodeip, wait=900)

    print 'Given Nodes are down... Waiting for nodes to come back'
    for node in nodes:
        user, hostip = node.split('@')
        count = 0
        while not verify_sshd(hostip,
                user,
                env.passwords[node]):
            sys.stdout.write('.')
            sleep(int(interval))
            count+=1
            if count <= int(attempts):
                continue
            else:
                print 'Timed out waiting for node (%s) to come back up...' %node
                sys.exit(1)
    return 0

def enable_haproxy():
    ''' For Ubuntu. Set ENABLE=1 in /etc/default/haproxy
    '''
    if detect_ostype() == 'ubuntu':
        with settings(warn_only=True):
            sudo("sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy")
#end enable_haproxy    

def qpidd_changes_for_ubuntu():
    '''Qpidd.conf changes for Ubuntu
    '''
    qpid_file = '/etc/qpid/qpidd.conf'
    if detect_ostype() == 'ubuntu':
        with settings(warn_only=True):
            sudo("sudo sed -i 's/load-module=\/usr\/lib\/qpid\/daemon\/acl.so/#load-module=\/usr\/lib\/qpid\/daemon\/acl.so/g' %s" %(qpid_file))
            sudo("sudo sed -i 's/acl-file=\/etc\/qpid\/qpidd.acl/#acl-file=\/etc\/qpid\/qpidd.acl/g' %s" %(qpid_file))
            sudo("sudo sed -i 's/max-connections=2048/#max-connections=2048/g' %s" %(qpid_file))
            sudo('grep -q \'auth=no\' %s || echo \'auth=no\' >> %s' %(qpid_file,qpid_file))
            sudo('service qpidd restart')
#end qpidd_changes_for_ubuntu

@task
def is_pingable(host_string, negate=False, maxwait=900):
    result = 0
    hostip = host_string.split('@')[1]
    starttime = datetime.datetime.now()
    timedelta = datetime.timedelta(seconds=int(maxwait))
    runouput = collections.namedtuple('runouput', 'return_code')
    with settings(host_string=host_string, warn_only=True):
       while True:
            try:
                res = sudo('ping -q -w 2 -c 1 %s' %hostip)
            except:
                res = runouput(return_code=1)
                
            if res.return_code == 0 and negate == 'False':
                print 'Host (%s) is Pingable'
                break
            elif res.return_code != 0 and negate == 'True':
                               print 'Host (%s) is Down' %hostip
                               break
            elif starttime + timedelta <= datetime.datetime.now():
                print 'Timeout while trying to ping host (%s)' %hostip
                result = 1
                break
            else:
                print 'Retrying...'
                time.sleep(1)
    return result

@roles('openstack')
@task
def increase_ulimits():
    '''
    Increase ulimit in /etc/init.d/mysqld /etc/init/mysql.conf /etc/init.d/rabbitmq-server files
    '''
    with settings(warn_only = True):
        if detect_ostype() == 'ubuntu':
            sudo("sed -i '/start|stop)/ a\    ulimit -n 10240' /etc/init.d/mysql") 
            sudo("sed -i '/start_rabbitmq () {/a\    ulimit -n 10240' /etc/init.d/rabbitmq-server")
            sudo("sed -i '/umask 007/ a\limit nofile 10240 10240' /etc/init/mysql.conf")
            sudo("sed -i '/\[mysqld\]/a\max_connections = 10000' /etc/mysql/my.cnf")
            sudo("echo 'ulimit -n 10240' >> /etc/default/rabbitmq-server")
        else:
            sudo("sed -i '/start(){/ a\    ulimit -n 10240' /etc/init.d/mysqld")
            sudo("sed -i '/start_rabbitmq () {/a\    ulimit -n 10240' /etc/init.d/rabbitmq-server")
            sudo("sed -i '/\[mysqld\]/a\max_connections = 2048' /etc/my.cnf")

@roles('cfgm','database','control','collector')
@task
def increase_limits():
    '''
    Increase limits in /etc/security/limits.conf, sysctl.conf and /etc/contrail/supervisor*.conf files
    '''
    limits_conf = '/etc/security/limits.conf'
    with settings(warn_only = True):
        pattern='^root\s*soft\s*nproc\s*.*'
        if detect_ostype() in ['ubuntu']:
            line = 'root soft nofile 65535\nroot hard nofile 65535'
        else:
            line = 'root soft nproc 65535'
        insert_line_to_file(pattern = pattern, line = line,file_name = limits_conf)

        pattern='^*\s*hard\s*nofile\s*.*'
        line = '* hard nofile 65535'
        insert_line_to_file(pattern = pattern, line = line,file_name = limits_conf)

        pattern='^*\s*soft\s*nofile\s*.*'
        line = '* soft nofile 65535'
        insert_line_to_file(pattern = pattern, line = line,file_name = limits_conf)

        pattern='^*\s*hard\s*nproc\s*.*'
        line = '* hard nproc 65535'
        insert_line_to_file(pattern = pattern, line = line,file_name = limits_conf)

        pattern='^*\s*soft\s*nproc\s*.*'
        line = '* soft nofile 65535'
        insert_line_to_file(pattern = pattern, line = line,file_name = limits_conf)

        sysctl_conf = '/etc/sysctl.conf'
        insert_line_to_file(pattern = '^fs.file-max.*',
                line = 'fs.file-max = 65535',file_name = sysctl_conf)
        sudo('sysctl -p')

        sudo('sed -i \'s/^minfds.*/minfds=10240/\' /etc/contrail/supervisor*.conf')

#end increase_limits

def insert_line_to_file(line,file_name,pattern=None):
    with settings(warn_only = True):
        if pattern:
            sudo('sed -i \'/%s/d\' %s' %(pattern,file_name))
        sudo('printf "%s\n" >> %s' %(line, file_name))
#end insert_line_to_file

@roles('build')
@task
def full_mesh_ping_by_name():
    for host in env.roledefs['all']:
        with settings(host_string = host, warn_only = True):
            for hostname in env.hostnames['all']:
                result = sudo('ping -c 1 %s' %(hostname))
                if not result.succeeded:
                    print '!!! Ping from %s to %s failed !!!' %( host, hostname)
                    exit(1)
    print "All nodes are able to ping each other using hostnames"
#end full_mesh_ping

@roles('build')
@task
def validate_hosts():
    all_hostnames = env.hostnames['all']
    current_hostlist = {}
    current_hosttimes = {}
    
    # Check if the hostnames on the nodes are as mentioned in testbed file
    for host in env.roledefs['all']:
        with settings(host_string = host):
            curr_hostname = sudo('hostname')
            if not curr_hostname  in all_hostnames:
                print "Hostname of host %s : %s not defined in testbed!!!" %(
                    host, curr_hostname)
                exit(1)
            if not curr_hostname  in current_hostlist.keys() :
                current_hostlist[curr_hostname] = host
            else:
                print "Hostname %s assigned to more than one host" %(curr_hostname)
                print "They are %s and %s" %(hstr_to_ip(host), hstr_to_ip(current_hostlist[curr_hostname]))
                print "Please fix them before continuing!! "
                exit(1)
    
    #Check if env.hostnames['all'] has any spurious entries
    if set(current_hostlist.keys()) != set(env.hostnames['all']):
        print "hostnames['all'] in testbed file does not seem to be correct"
        print "Expected : %s" %(current_hostlist)
        print "Seen : %s" %(env.hostnames['all']) 
        exit(1)
    print "All hostnames are unique and defined in testbed correctly..OK"
    
    #Check if date/time on the hosts are almost the same (diff < 5min)
    for host in env.roledefs['all']:
        with settings(host_string = host):
            current_hosttimes[host] = sudo('date +%s')
    avg_time = sum(map(int,current_hosttimes.values()))/len(current_hosttimes.values())
    for host in env.roledefs['all']:
        print "Expected date/time on host %s : (approx) %s, Seen : %s" %(
            host,
            datetime.datetime.fromtimestamp(avg_time),
            datetime.datetime.fromtimestamp(float(current_hosttimes[host])))
        if abs(avg_time - int(current_hosttimes[host])) > 300 : 
            print "Time of Host % seems to be not in sync with rest of the hosts" %(host)
            print "Please make sure that the date and time on all hosts are in sync before continuning!!"
            exit(1)

    print "Date and time on all hosts are in sync..OK"
    
    # Check if all hosts are reachable by each other using their hostnames
    execute(full_mesh_ping_by_name)
        

@task
@roles('openstack')
def reboot_vm(vmid='all', mode='soft'):
    flag = ''
    if mode == 'hard':
        flag = '--hard'

    if vmid != 'all':
        with settings(warn_only=True):
            sudo('source /etc/contrail/openstackrc; nova reboot %s %s' % (flag, vmid))
        return

    print "Rebooting all the VM's"
    nova_list = run ("source /etc/contrail/openstackrc; nova list --all-tenants")
    nova_list = nova_list.split('\r\n')
    nova_list = nova_list[3:-1]
    for vm_info in nova_list:
        vm_id = vm_info.split('|')[1]
        with settings(warn_only=True):
            sudo('source /etc/contrail/openstackrc; nova reboot %s %s' % (flag, vm_id))

@task
@roles('database')
def delete_cassandra_db_files():
    if exists('/home/cassandra/'):
        db_path = '/home/cassandra/'
    else:
        db_path = '/var/lib/cassandra/'

    sudo('rm -rf %s/commitlog' %(db_path))
    sudo('rm -rf %s/data' %(db_path))
    sudo('rm -rf %s/saved_caches' %(db_path))


@task
@roles('build')
def pre_check():
    database_nodes = deepcopy(env.roledefs['database'])
    if (len(database_nodes) % 2) != 1:
        print "\nERROR: \n\tRecommended to deploy odd number of zookeeper(database) nodes."
        print "\tAdd/remove a node to/from the existing clusters testbed.py and continue."
        exit(0)
    execute('verify_time_all')
    if len(env.roledefs['openstack']) > 1 and not get_openstack_internal_vip():
        print "\nERROR: \n\tkeystone_ip(VIP) needs to be set in testbed.py for HA, when more than one openstack node is defined."
        exit(1)
    if (len(env.roledefs['openstack']) > 1 and
        env.roledefs['openstack'].sort() == env.roledefs['cfgm'].sort() and
        get_openstack_internal_vip() != get_openstack_internal_vip()):
        print "\nERROR: \n\tOpenstack and cfgm nodes are same, No need for contrail_internal_vip to be specified in testbed.py."
        exit(1)
    if (len(env.roledefs['openstack']) > 1 and
        env.roledefs['openstack'].sort() != env.roledefs['cfgm'].sort() and
        get_openstack_internal_vip() == get_openstack_internal_vip()):
        print "\nERROR: \n\tOpenstack and cfgm nodes are different, Need to specify  contrail_internal_vip testbed.py."
        exit(1)
        print "\nERROR: \n\tOpenstack and cfgm nodes are same, No need for contrail_internal_vip to be specified in testbed.py."

def role_to_ip_dict(role=None):
    role_to_ip_dict = {}
    for each_key in env.roledefs:
        role_to_ip_dict[each_key] = [
            hstr_to_ip(
                get_control_host_string(each_host)) for each_host in env.roledefs[each_key]]
    if role is not None:
        print role_to_ip_dict[role]
        return role_to_ip_dict[role]
    print role_to_ip_dict
    return role_to_ip_dict
# end role_to_ip_dict_utility

def round_robin_collector_ip_assignment(all_node_ips, collector_ips):
    '''
    From the node IP and collector IPs create a dictionary to do a static mapping of remote nodes to connect to collectors
    which can be refered to by rsyslog clients. The connection principle followed here for remote clients is on a round robin
    basis of servers.
    '''
    mapping_dict = {}
    ind = -1
    for node_ip in all_node_ips:
        flag = 0
        for coll_ip in collector_ips:
            if node_ip == coll_ip:
                mapping_dict[node_ip] = coll_ip
                flag = 1
                break
        if flag != 1:
            ind += 1
            if ind == len(collector_ips):
                ind = 0
            mapping_dict[node_ip] = collector_ips[ind]

    return mapping_dict
# end of round_robin_collector_ip_assignment

@task
def disable_iptables():
    with settings(warn_only=True):
        os_type = detect_ostype().lower()
        if os_type in ['centos']:
            sudo("iptables --flush")
            sudo("service iptables save")
        if os_type in ['redhat']:
            sudo("iptables --flush")
            sudo("sudo service iptables stop")
            sudo("sudo service ip6tables stop")
            sudo("sudo systemctl stop firewalld")
            sudo("sudo systemctl status firewalld")
            sudo("sudo chkconfig firewalld off")
            sudo("sudo /usr/libexec/iptables/iptables.init stop")
            sudo("sudo /usr/libexec/iptables/ip6tables.init stop")
            sudo("sudo service iptables save")
            sudo("sudo service ip6tables save")
            sudo("iptables -L")

@task
@roles('all')
def set_allow_unsupported_sfp():
    with settings(warn_only=True):
        sudo("sed -i '/options ixgbe allow_unsupported_sfp/d' /etc/modprobe.d/ixgbe.conf")
        sudo('echo "options ixgbe allow_unsupported_sfp=1" >> /etc/modprobe.d/ixgbe.conf')
        sudo('rmmod ixgbe; modprobe ixgbe')

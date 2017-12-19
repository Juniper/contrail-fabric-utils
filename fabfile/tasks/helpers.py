import re
import sys
import os
import time
import tempfile
from copy import deepcopy
import collections
from os.path import expanduser, normpath, basename

from fabfile.config import *
import fabfile.common as common
from fabfile.utils.host import *
from fabfile.utils.multitenancy import *
from fabfile.utils.fabos import *
from fabric.contrib.files import exists
import datetime
from fabfile.tasks.esxi_defaults import apply_esxi_defaults
from fabfile.utils.cluster import get_orchestrator, get_all_hostnames, get_hostname
from fabfile.utils.analytics import get_analytics_data_dir, get_minimum_diskGB
from fabfile.tasks.ntp import setup_ntp, setup_ntp_node
from fabfile.utils.fabos import detect_ostype, is_package_installed, is_liberty_or_above

@task
def copydir(src_path, dst_path=None, src_host='localhost', dst_host=None):
    if not dst_host:
        raise RuntimeError("Please specify destination host")
    if not dst_path:
        dst_path = src_path
    src_path = (normpath(expanduser(src_path)))
    dst_path = normpath(expanduser(dst_path))
    if not src_host == 'localhost':
        with settings(host_string=src_host,
                      password=get_env_passwords(src_host)):
            tmpdir = tempfile.mkdtemp()
            get_as_sudo(src_path, tmpdir)
            src_path = os.path.join(tmpdir, basename(src_path))
    with settings(host_string=dst_host,
                  password=get_env_passwords(dst_host)):
        sudo('mkdir -p %s' % dst_path)
        put('%s/*' % src_path, dst_path, use_sudo=True)


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
                          get_env_passwords(host_string)):
            sys.stdout.write('.')
            sleep(2)
            count+=1
            if count <=1000:
                continue
            else:
                print 'Timed out waiting for node to come back up'
                sys.exit(1)
# end compute_reboot

def reimage_virtual_nodes(host, count):
    with settings(
            host_string='%s@%s' % (
            env.virtual_nodes_info[host]['keystone_user'],
            env.virtual_nodes_info[host]['keystone_ip']),
            password=env.virtual_nodes_info[host]['keystone_pass'],
            warn_only=True, abort_on_prompts=False, debug=True):
        common_agrs = '--os-username %s --os-password %s --os-tenant-name %s \
                       --os-auth-url http://%s:5000/v2.0/' \
                       % (env.virtual_nodes_info[host]['user'],
                         env.virtual_nodes_info[host]['password'],
                         env.virtual_nodes_info[host]['tenant'],
                         env.virtual_nodes_info[host]['keystone_authip'])
        for i in range(10):
            status = run(
                "nova %s delete %s" %
                (common_agrs, get_hostname(host)))
            sleep(5)
            check = run(
                "nova %s show %s | grep 'status'" %
                (common_agrs, get_hostname(host)))
            if 'status' in check:
                if i > 5:
                    print 'Timed out waiting for vm to get deleted aborting'
                    sys.exit(1)
                else:
                    print 'Waiting for vm to get deleted'
                    sleep(5)
            else:
                break
        status = run(
            "neutron %s port-create --tenant-id %s --mac-address %s \
             --fixed-ip ip_address=%s --name %s %s" \
                         % (common_agrs,
                         env.virtual_nodes_info[host]['tenant_id'],
                         env.virtual_nodes_info[host]['mac-address'],
                         host.split('@')[1],
                         get_hostname(host),
                         env.virtual_nodes_info[host]['vn_id']))
        m = re.search('\|\sid(.*)\|\s([\w-]+)(.*)\|', status)
        port_id = m.group(2)
        sleep(5)
        run("nova %s boot --flavor %s --image %s --nic port-id=%s  %s" \
                         % (common_agrs,
                         env.virtual_nodes_info[host]['flavor'],
                         env.virtual_nodes_info[host]['image_name'],
                         port_id,
                         get_hostname(host)))

        for i in range(10):
            check = run(
                "nova %s show %s | grep 'status'" %
                (common_agrs, get_hostname(host)))
            if 'ACTIVE' not in check:
                if i > 5:
                    print 'Timed out waiting for vm to become Active'
                    sys.exit(1)
                else:
                    print 'Waiting for vm to get Active'
                    sleep(5)
            else:
                break


@roles('build')
@task
def all_reimage(build_param="@LATEST"):
    count = 0
    for host in env.roledefs["all"]:
        if 'virtual_nodes_info' in env.keys() and  host in env.virtual_nodes_info.keys():
              reimage_virtual_nodes(host, count)
              count = count + 1

        else:
            hostname = get_hostname(host)
            if 'ostypes' in env.keys():
                if 'xen' in env.ostypes[host]:
                    pass
                elif 'ubuntu1404' == env.ostypes[host]:
                    base_img = 'ubuntu-14.04'
                elif 'ubuntu' in env.ostypes[host]:
                    base_img = 'ubuntu-12.04.3'
                elif 'centos70' == env.ostypes[host]:
                    base_img = 'centos-7.0'
                elif 'centos71' == env.ostypes[host]:
                    base_img = 'centos-7.1'
                elif 'centos65' == env.ostypes[host]:
                    base_img = 'centos-6.5'
                elif 'centos' in env.ostypes[host]:
                    base_img = 'centos-6.4'
                elif 'redhat70' in env.ostypes[host]:
                    base_img = 'redhat-7.0'
                elif 'redhat' in env.ostypes[host]:
                    base_img = 'redhat'
                with settings(warn_only=True):
                    local(
                        "/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s %s" %
                        (hostname, base_img))
            else:
                # CentOS
                    local(
                        "/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s centos-6.5" %
                        (hostname))
            sleep(5)
# end all_reimage

@roles('build')
@task
def all_sm_reimage(build_param=None,smgr_client='/cs-shared/server-manager/client/server-manager'):
    hosts = env.roledefs['all'][:]
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    cluster_id=None
    try:
        cluster_id=env.cluster_id
    except:
        sys.stdout.write('No cluster_id specified in testbed file.\n')        
        sys.stdout.write('Reimage will be done on per node basis.\n')

    if ((cluster_id is not None) and (not esxi_hosts)):
        reimage_cmd=smgr_client + ' reimage --no_confirm --cluster_id '
        if build_param is not None:
            with settings(warn_only=True):
                reimage_cmd = reimage_cmd + '%s %s' % (cluster_id,build_param)
                local(reimage_cmd)
        else:
            if 'ostypes' in env.keys():
                if 'ubuntu' in env.ostypes[env.ostypes.keys()[0]]:
                    with settings(warn_only=True):
                        reimage_cmd = reimage_cmd + '%s ubuntu-12.04.3' % cluster_id
                        local(reimage_cmd)
                else:
                    # CentOS
                    with settings(warn_only=True):
                        reimage_cmd = reimage_cmd + '%s centos-6.4' % cluster_id
                        local(reimage_cmd)
            else:
                # CentOS
                with settings(warn_only=True):
                    reimage_cmd = reimage_cmd + '%s centos-6.4' % cluster_id
                    local(reimage_cmd)
            sleep(1)
        sleep(30)
    else:
        if esxi_hosts:
            for k,v in esxi_hosts.items():
                if 'contrail_vm' in v:#In vcenter gateway,contrail_vm not there
                    hosts.remove(v['contrail_vm']['host'])
        for host in hosts:
            hostname = get_hostname(host)
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
            count=0
            image="esx5.5"
            for esxi in esxi_hosts:
                if 'skip_reimage' not in esxi_hosts[esxi]:#Its a hack to avoid reimage of the esxi servers
                    count=count+1
                    image_id=image + "-" + str(count)
                    with settings(warn_only=True):
                        local("/cs-shared/server-manager/client/server-manager reimage --no_confirm --server_id %s %s" % (esxi,image_id))
                        sleep(10)
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
        password = get_env_passwords(host_string)
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
    #run(command)
#end all_command

@roles('all')
@task
def all_ping():
    for host in get_all_hostnames():
        local("ping -c 1 -q %s " %(host))

#end all_ping

def ping_test(host_string):
    with settings(host_string=host_string, warn_only = True):
        result = local("ping -c 1 -q %s" % hstr_to_ip(host_string))
        if result.return_code == 0:
            return True
        else:
            return False

@roles('all')
@task
def all_version():
    sudo("contrail-version")
#end all_ping

@roles('all')
@task
def check_reimage_state():
    failed_host = []
    hosts = get_all_hostnames()[:]
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            try:
                if env['host_string'] == esxi_hosts[esxi]['contrail_vm']['host']:
                    print "skipping contrail vm, continue..."
                    return
            except Exception as e:
                print "%s"%e
                return #Handling the exception if contrail-vm not present in testbed.py,
                       #which is the case for vcenter gateway
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
    if get_orchestrator is 'openstack':
       sudo("service contrail-svc-monitor status")
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


@task
def add_images(image=None):
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
               ("sugarcrm.vmdk", "sugarcrm") ,
               ("docker/phusion-baseimage-enablesshd.tar", "phusion-baseimage-enablesshd"),
             ]

    for (loc, name) in images:
        if image is not None and image != name:
            continue
        local = "/images/"+loc+".gz"
        remote = loc.split("/")[-1]
        remote_gz = remote+".gz"
        glance_host = env.roledefs['openstack'][0]
        if 'docker' in loc:
            if env.get('hypervisor', None):
                docker_nodes = filter(lambda (node, hypervisor): hypervisor == 'docker',
                                      env.hypervisor.items())
                if docker_nodes:
                    # First docker compute
                    glance_host = docker_nodes[0][0]
                else:
                    print "No compute is provisioned with docker as hypervisor. Skipping..."
                    continue
        with settings(host_string=glance_host):
            mount = None
            if '10.84' in env.host_string:
                mount = '10.84.5.120/cs-shared'
            elif '10.204' in env.host_string:
                mount = '10.204.217.158'
            if not mount:
                return
            sudo("wget http://%s/%s" % (mount, local))
            sudo("gunzip " + remote_gz)

            os_type = detect_ostype()
            openstack_sku = get_openstack_sku()
            liberty_or_above = is_liberty_or_above()

            if liberty_or_above:
                cmd = "source /etc/contrail/openstackrc; {PRECMD}"\
                      " glance --insecure image-create --name {IMGNAME}"\
                      " --visibility public --container-format {IMGFORMAT}"\
                      " --disk-format {DISKFORMAT} {IMGFILE_OPT}"
            else:
                cmd = "source /etc/contrail/openstackrc; {PRECMD}"\
                      " glance --insecure image-create --name {IMGNAME}"\
                      " --is-public True --container-format {IMGFORMAT}"\
                  " --disk-format {DISKFORMAT} {IMGFILE_OPT}"
            if ".vmdk" in loc:
                glance_kwargs = {'PRECMD': '',
                                 'IMGNAME' : name,
                                 'IMGFORMAT' : 'ovf',
                                 'DISKFORMAT' : 'vmdk',
                                 'IMGFILE_OPT' : '--file %s' % remote}
            elif "docker" in loc:
                image_name = remote.split(".tar")[0]
                sudo("docker load -i %s" % remote)
                glance_kwargs = {'PRECMD': 'docker save %s |' % image_name,
                                 'IMGNAME' : name,
                                 'IMGFORMAT' : 'docker',
                                 'DISKFORMAT' : 'raw',
                                 'IMGFILE_OPT' : ''}
            else:
                glance_kwargs = {'PRECMD': '',
                                 'IMGNAME' : name,
                                 'IMGFORMAT' : 'ovf',
                                 'DISKFORMAT' : 'qcow2',
                                 'IMGFILE_OPT' : '--file %s' % remote}
            sudo(cmd.format(**glance_kwargs))
            sudo("rm %s" % remote)
#end add_images

def preload_image_to_esx(url, glance_id, sizes, version):
    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if not esxi_hosts:
        return
    for esxi in esxi_hosts.values():
        try:
            if esxi['contrail_vm']['host'] in env.roledefs['compute']:
                apply_esxi_defaults(esxi)
                # for havana(2013.2), images are stored under datastore/vmware_base/
                base = esxi['datastore'] + 'vmware_base/'
                # for icehouse, images are stored under datstore/<ip>_base/<glanceid>/
                if '2014.1' in version:
                    ip = esxi['contrail_vm']['host'].split('@')[-1]
                    base = esxi['datastore'] + '/' + ip + '_base/' + glance_id + '/'

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
        except Exception as e:
            print "%s"%e
            pass #Handling exception for vcenter gateway

#end preload_images_to_esx

@hosts(*env.roledefs['openstack'][0:1])
@task
def add_basic_images(image=None):
    mount=None
    if '10.84' in env.host:
        mount= '10.84.5.120/cs-shared'
    elif '10.204' in env.host:
        mount= '10.204.217.158'
    if not mount :
        return

    openstack_version  = run("source /etc/contrail/openstackrc; nova-manage version")

    images = [ ("converts/ubuntu.vmdk", "ubuntu", [10,20]),
               ("converts/ubuntu-traffic.vmdk", "ubuntu-traffic", [10,20]),
               ("converts/centos-min.vmdk", "centos65-ipv6", [10]),
               ("converts/ubuntu-dhcp-server.vmdk", "ubuntu-dhcp-server", []),
               ("converts/cirros-0.3.0-x86_64-disk.vmdk", "cirros", [1,10]),
               ("vsrx/junos-vsrx-12.1-in-network.img", "vsrx", []),
               ("analyzer/analyzer-vm-console.qcow2", "analyzer", []),
               ("converts/ubuntu-dns-server.vmdk", "ubuntu-dns-server", []),
               ("converts/ubuntu-dhcpdns-server.vmdk", "ubuntu-dhcpdns-server", []),
               ("tinycore/tinycore-in-network-nat.qcow2", "tiny_nat_fw", []),
               ("tinycore/tinycore-in-network.qcow2", "tiny_in_net", []),
               ("tinycore/tinycore-net-transparent-fw.qcow2", "tiny_trans_fw", []),

               ]

    for (loc, name, sizes) in images:
        if image is not None and image != name:
            continue
        local = "/images/"+loc+".gz"
        remote = loc.split("/")[-1]
        remote_gz = remote+".gz"
        run("wget http://%s/%s" % (mount, local))
        run("gunzip " + remote_gz)

        os_type = detect_ostype()
        openstack_sku = get_openstack_sku()
        liberty_or_above = is_liberty_or_above()

        if liberty_or_above:
            if ".vmdk" in loc:
                if 'converts' in loc:
                    glance_id = run("(source /etc/contrail/openstackrc; glance --insecure image-create --name '"+name+"' --visibility public --container-format bare --disk-format vmdk --property vmware_disktype='sparse' --property vmware_adaptertype='ide' < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
                else:
                    glance_id = run("(source /etc/contrail/openstackrc; glance --insecure add name='"+name+"' --visibility public container_format=ovf disk_format=vmdk < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
                if glance_id.succeeded:
                    preload_image_to_esx('http://%s/%s' % (mount,local), glance_id, sizes, openstack_version)
            else:
                run("(source /etc/contrail/openstackrc; glance --insecure image-create --name '"+name+"' --visibility public --container-format ovf --disk-format qcow2 --property hypervisor_type=qemu < "+remote+")")
        else:
            if ".vmdk" in loc:
                if 'converts' in loc:
                    glance_id = run("(source /etc/contrail/openstackrc; glance --insecure image-create --name '"+name+"' --is-public True --container-format bare --disk-format vmdk --property vmware_disktype='sparse' --property vmware_adaptertype='ide' < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
                else:
                    glance_id = run("(source /etc/contrail/openstackrc; glance --insecure add name='"+name+"' is_public=true container_format=ovf disk_format=vmdk < "+remote+" | grep -e 'id\>' | awk '{printf $4}')")
                if glance_id.succeeded:
                    preload_image_to_esx('http://%s/%s' % (mount,local), glance_id, sizes, openstack_version)
            else:
                run("(source /etc/contrail/openstackrc; glance --insecure image-create --name '"+name+"' --is-public True --container-format ovf --disk-format qcow2 --property hypervisor_type=qemu < "+remote+")")

        run("rm "+remote)

#end add_basic_images

@hosts(*env.roledefs['openstack'][0:1])
@task
def add_basic_flavors(flavor=None):
    flavors = [ ("m1.tiny", "1", "1",  "512"),
               ("m1.small", "1", "20",  "2048"),
               ("m1.medium", "1", "40",  "4096"),
               ("m1.large", "1", "80",  "8192"),
               ("m1.xlarge", "1", "160",  "16384")
               ]

    flavors_present = run("(source /etc/contrail/openstackrc; openstack flavor list)")

    for (name, vcpus, disk, ram) in flavors:
        if (flavor is not None and flavor != name
                or name in flavors_present):
            if name in flavors_present:
                print "%s already present, not adding it" % name
            continue
        run("(source /etc/contrail/openstackrc; openstack flavor create --public '"+name+"' --id auto --ram '"+ram+"' --disk '"+disk+"' --vcpus '"+vcpus+"')")
#end add_basic_flavors

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
    os_opts = os_opts + ' --os-username %s --os-password %s ' % get_authserver_credentials()
    os_opts = os_opts + ' --os-tenant-name %s ' % get_admin_tenant_name()
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

@roles('openstack')
def cleanup_os_config():
    '''
    This has to be run from reset_config() task only
    '''
    dbs=['nova', 'mysql', 'keystone', 'glance', 'cinder','heat']
    services =['mysqld', 'openstack-nova-novncproxy', 'rabbitmq-server', 'openstack-cinder-volume', 'openstack-cinder-scheduler', 'openstack-cinder-api', 'openstack-glance-registry', 'openstack-glance-api', 'openstack-nova-xvpvncproxy', 'openstack-nova-scheduler', 'openstack-nova-objectstore', 'openstack-nova-metadata-api', 'openstack-nova-consoleauth', 'openstack-nova-console', 'openstack-nova-compute', 'openstack-nova-cert', 'openstack-nova-api', 'openstack-keystone']
    ubuntu_services =['mysql', 'nova-novncproxy', 'rabbitmq-server', 'cinder-volume', 'cinder-scheduler', 'cinder-api', 'glance-registry', 'glance-api', 'nova-xvpvncproxy', 'nova-scheduler', 'nova-objectstore', 'nova-metadata-api', 'nova-consoleauth', 'nova-console', 'nova-compute', 'nova-cert', 'nova-api', 'contrail-vncserver', 'keystone', ]
    # Drop all dbs
    with settings(warn_only=True):
        sudo('mysqladmin -u root -p$(cat /etc/contrail/mysql.token) password \'\' ')
        for db in dbs:
            sudo('mysql -u root -e \'drop database %s;\''  %(db))

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
            sudo('sudo rm -rf /var/lib/glance/images/*')

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
def ping_hostip(hostip='127.0.0.0'):
    cmd = 'ping -c 3 -q %s' %hostip
    output = 0
    with settings(hide('running'), warn_only=True):
        try:
            output=local(cmd,capture=True)
        except:
            pass
    if " 100% packet loss" in str(output):
        output=0
    else:
        output=1
    return output

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
                    try:
                        nodes.remove(esxi_hosts[esxi]['contrail_vm']['host'])
                    except Exception as e:
                        print "%s"%e
                        pass #Handing exception for vcenter gateway
                             #Entry for contrail_vm not there in testbed.py

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

        print 'Trying to ping node - %s' %hostip
        while not ping_hostip(hostip):
            sys.stdout.write('.')
            sleep(int(interval))
            count+=1
            if count <= int(attempts):
                continue
            else:
                print 'Ping failed to host - %s' %hostip
                sys.exit(1)

        while not verify_sshd(hostip,
                user,
                get_env_passwords(node)):
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

@task
def setup_hugepages_node(*args):
    """Setup hugepages on one or list of nodes
    USAGE: fab setup_hugepages_node:user@host1,user@host2,...
    """

    # How many times DPDK inits hugepages (rte_eal_init())
    # See function map_all_hugepages() in DPDK
    DPDK_HUGEPAGES_INIT_TIMES = 2

    for host_string in args:
        dpdk = getattr(env, "dpdk", {})
        if host_string not in dpdk:
            print "Host %s is not dpdk enabled, not configuring hugepages" \
                % host_string
            return

        # get required size of hugetlbfs
        factor = int(dpdk[host_string]['huge_pages'])

        if factor == 0:
            factor = 1

        with settings(host_string=host_string):
            # set number of huge pages
            memsize = sudo("grep MemTotal /proc/meminfo | tr -s ' ' | cut -d' ' -f 2")
            pagesize = sudo("grep Hugepagesize /proc/meminfo | tr -s ' ' | cut -d' ' -f 2")
            reserved = sudo("grep HugePages_Total /proc/meminfo | tr -s ' ' | cut -d' ' -f 2")

            if (reserved == ""):
                reserved = "0"

            requested = ((int(memsize) * factor) / 100) / int(pagesize)

            if (requested > int(reserved)):
                pattern = "^vm.nr_hugepages ="
                line = "vm.nr_hugepages = %d" %requested
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/sysctl.conf')

            current_max_map_count = sudo("sysctl -n vm.max_map_count")
            if current_max_map_count == "":
                current_max_map_count = 0

            current_huge_pages = max(int(requested), int(reserved))

            requested_max_map_count = DPDK_HUGEPAGES_INIT_TIMES * int(current_huge_pages)
            if int(requested_max_map_count) > int(current_max_map_count):
                pattern = "^vm.max_map_count ="
                line = "vm.max_map_count = %d" %requested_max_map_count
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/sysctl.conf')

            mounted = sudo("mount | grep hugetlbfs | cut -d' ' -f 3")
            if (mounted != ""):
                print "hugepages already mounted on %s" %mounted
            else:
                sudo("mkdir -p /hugepages")
                pattern = "^hugetlbfs"
                line = "hugetlbfs    /hugepages    hugetlbfs defaults      0       0"
                insert_line_to_file(pattern = pattern, line = line,
                                    file_name = '/etc/fstab')
                sudo("mount -t hugetlbfs hugetlbfs /hugepages")

@roles('compute')
@task
def setup_hugepages():
    setup_hugepages_node(env.host_string)

@task
def undo_setup_hugepages_node(*args):
    """Unmounts hugepages and deletes related config made by 'setup_hugepages'
    It can be executed ONLY on the dpdk enabled hosts (as stated in testbed.py
    file).
    Usage: fab undo_setup_hugepages_node:user@1.1.1.1,user@2.2.2.2
    """
    for host_string in args:
        if host_string not in getattr(env, "dpdk", {}):
            print "Host %s is not dpdk enabled, not touching hugepages setup" \
                % host_string
            return

        with settings(host_string=host_string):
            if sudo("mount | grep hugetlbfs", warn_only=True):
                sudo("umount /hugepages")
            remove_pattern_from_file("^\s*hugetlbfs.*hugetlbfs.*$",
                                     "/etc/fstab")
            remove_pattern_from_file("^\s*vm\.max_map_count\s*=.*$",
                                     "/etc/sysctl.conf")

@roles('compute')
@task
def undo_setup_hugepages():
    undo_setup_hugepages_node(env.host_string)

@task
def setup_coremask_node(*args):
    """Setup core mask on one or list of nodes
    USAGE: fab setup_coremask_node:user@host1,user@host2,...
    """
    vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'

    for host_string in args:
        dpdk = getattr(env, 'dpdk', None)
        if dpdk:
            if host_string in dpdk:
                try:
                    coremask = dpdk[host_string]['coremask']
                except KeyError:
                    raise RuntimeError("Core mask for host %s is not defined." \
                        %(host_string))
            else:
                print "No %s in the dpdk section in testbed file." \
                    %(host_string)
                return
        else:
            print "No dpdk section in testbed file on host %s." %(host_string)
            return

        if not coremask:
            raise RuntimeError("Core mask for host %s is not defined." \
                % host_string)

        # if a list of cpus is provided, -c flag must be passed to taskset
        if (',' in coremask) or ('-' in coremask):
            taskset_param = ' -c'
        else:
            taskset_param = ''

        with settings(host_string=host_string):
            # supported coremask format: hex: (0x3f); list: (0,3-5), (0,1,2,3,4,5)
            # try taskset on a dummy command
            if sudo('taskset%s %s true' %(taskset_param, coremask), quiet=True).succeeded:
                sudo('sed -i \'s/command=/command=taskset%s %s /\' %s' \
                    %(taskset_param, coremask, vrouter_file))
            else:
                raise RuntimeError("Error: Core mask %s for host %s is invalid." \
                    %(coremask, host_string))

@task
def setup_uio_driver(*args):
    """Setup UIO driver to use for DPDK (igb_uio, uio_pci_generic or vfio-pci)
    USAGE: fab setup_uio_driver:user@host1,user@host2,...
    """
    vrouter_agent_file = '/etc/contrail/contrail-vrouter-agent.conf'

    for host_string in args:
        dpdk = getattr(env, 'dpdk', None)
        if dpdk:
            if host_string in dpdk:
                if 'uio_driver' in dpdk[host_string]:
                    uio_driver = dpdk[host_string]['uio_driver']
                else:
                    print "No UIO driver defined for host %s, skipping..." \
                        %(host_string)
                    return
            else:
                print "No host %s defined in the dpdk section, skipping..." \
                    %(host_string)
                return
        else:
            print "No env.dpdk section in testbed file, skipping the configuration..."
            return

        if not uio_driver:
            raise RuntimeError("UIO driver for host %s is not defined." \
                % host_string)

        with settings(host_string=host_string):
            if sudo('modprobe %s' %(uio_driver), quiet=True).succeeded:
                print "Setting UIO driver to %s for host %s..." % (uio_driver,
                    host_string)
                sudo('sed -i.bak \'s/physical_uio_driver=.*/physical_uio_driver=%s/\' %s' \
                    %(uio_driver, vrouter_agent_file))
            else:
                raise RuntimeError("Error: invalid UIO driver %s for host %s" \
                    %(uio_driver, host_string))

@roles('openstack')
@task
def increase_ulimits():
    '''
    Increase ulimit in /etc/init.d/mysqld /etc/init/mysql.conf /etc/init.d/rabbitmq-server files
    '''
    execute('increase_ulimits_node', env.host_string)

@task
def increase_ulimits_node(*args):
    for host_string in args:
        with settings(host_string=host_string, warn_only = True):
            ostype = detect_ostype()
            if ostype == 'ubuntu':
                sudo("sed -i '/start|stop)/ a\    ulimit -n 10240' /etc/init.d/mysql")
                sudo("sed -i '/start_rabbitmq () {/a\    ulimit -n 10240' /etc/init.d/rabbitmq-server")
                sudo("sed -i '/umask 007/ a\limit nofile 10240 10240' /etc/init/mysql.conf")
                sudo("sed -i '/\[mysqld\]/a\max_connections = 10000' /etc/mysql/my.cnf")
                sudo("echo 'ulimit -n 10240' >> /etc/default/rabbitmq-server")
            elif ostype == 'centoslinux':
                sudo("sed -i '/\[mysqld\]/a\open_files_limit = 10240' /etc/my.cnf")
                sudo("sed -i '/\[mysqld\]/a\max_connections = 2048' /etc/my.cnf")
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
    execute('increase_limits_node', env.host_string)
#end increase_limits

@task
def increase_limits_node(*args):
    for host_string in args:
        limits_conf = '/etc/security/limits.conf'
        with  settings(host_string=host_string, warn_only=True):
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
            line = 'fs.file-max = 165535',file_name = sysctl_conf)
            sudo('sysctl -p')

            sudo('sed -i \'s/^minfds.*/minfds=10240/\' /etc/contrail/supervisor*.conf')
#end increase_limits

@roles('cfgm','database','collector')
@task
def increase_limits_no_control():
    '''
    Increase limits in /etc/security/limits.conf, sysctl.conf and /etc/contrail/supervisor*.conf files
    '''
    execute('increase_limits_node', env.host_string)
#end increase_limits_no_control

def insert_line_to_file(line,file_name,pattern=None):
    with settings(warn_only = True):
        if pattern:
            sudo('sed -i \'/%s/d\' %s' %(pattern,file_name))
        sudo('printf "%s\n" >> %s' %(line, file_name))
#end insert_line_to_file

def remove_pattern_from_file(pattern, file_name):
    with settings(warn_only = True):
        sudo('sed -i \'/%s/d\' %s' % (pattern, file_name))

@roles('build')
@task
def full_mesh_ping_by_name():
    for host in env.roledefs['all']:
        with settings(host_string = host, warn_only = True):
            for hostname in get_all_hostnames():
                result = sudo('ping -c 1 %s' %(hostname))
                if not result.succeeded:
                    print '!!! Ping from %s to %s failed !!!' %( host, hostname)
                    exit(1)
    print "All nodes are able to ping each other using hostnames"
#end full_mesh_ping

@roles('build')
@task
def validate_hosts():
    all_hostnames = get_all_hostnames()
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

    #Check if env.hostnames has any spurious entries
    if set(current_hostlist.keys()) != set(get_all_hostnames()):
        print "hostnames['all'] in testbed file does not seem to be correct"
        print "Expected : %s" %(current_hostlist)
        print "Seen : %s" %(get_all_hostnames())
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
@EXECUTE_TASK
@roles('database')
def check_disk_space():
    data_dir = get_analytics_data_dir()
    out = ''
    if data_dir is None:
        cmd = "sed -n '/data_file_directories/{n;p;}'"
        # If Ubuntu
        if exists('/etc/cassandra/cassandra.yaml', use_sudo=True):
            yaml_file = '/etc/cassandra/cassandra.yaml'
            out = sudo("%s %s" % (cmd, yaml_file))
        # If redhat distros
        elif exists('/etc/cassandra/conf/cassandra.yaml', use_sudo=True):
            yaml_file = '/etc/cassandra/conf/cassandra.yaml'
            out = sudo("%s %s" % (cmd, yaml_file))
        data_dir = out[2:]
    if not exists(data_dir, use_sudo=True):
        data_dir = '/var/lib'

    # Check space
    disk_cmd = "df -Pk " + data_dir + " | grep % | awk '{print $2}'"
    total_disk = sudo(disk_cmd)
    if (int(total_disk)/(1024*1024) < int(get_minimum_diskGB())):
        return False
    return True

@task
@roles('build')
def pre_check():
    result = execute('check_disk_space')
    nodes_without_minimum_space = filter(lambda node: node != None,
        map(lambda (node, met): node if not met else None, result.items()))
    if nodes_without_minimum_space:
        print "\nERROR: Minimum disk space(256GB) for analytics db is not met in nodes: %s"\
            % nodes_without_minimum_space
        print "\tPlease set 'minimum_diskGB' in testbed.py and continue."
        print "\tSpecifiy the avalilable disk space of database node in GB"
        print "\tHowever minimum disk space for database node is 256GB."
        exit(1)
    database_nodes = deepcopy(env.roledefs['database'])
    if (len(database_nodes) == 2):
        print "\nERROR: \n\tRecommended to deploy odd number of zookeeper(database) nodes."
        print "\tAdd/remove a node to/from the existing clusters testbed.py and continue."
        exit(1)
    execute('setup_ntp')
    execute('verify_time_all')
    # Assuming keystone_ip in env.keysone will be set only for external openstack
    # and is safer to skip this check
    if len(env.roledefs['openstack']) > 1 and not get_openstack_internal_vip() and \
       get_from_testbed_dict('keystone', 'keystone_ip', None) is None:
        print "\nERROR: \n\tkeystone_ip(VIP) needs to be set in testbed.py for HA, when more than one openstack node is defined."
        exit(1)
    if (len(env.roledefs['openstack']) > 1 and
        set(env.roledefs['openstack']) == set(env.roledefs['cfgm']) and
        get_openstack_internal_vip() != get_contrail_internal_vip()):
        print "\nERROR: \n\tOpenstack and cfgm nodes are same, No need for contrail_internal_vip to be specified in testbed.py."
        exit(1)
    if (len(env.roledefs['openstack']) > 1 and
        set(env.roledefs['openstack']) != set(env.roledefs['cfgm']) and
        get_openstack_internal_vip() == get_contrail_internal_vip()):
        print "\nERROR: \n\tOpenstack and cfgm nodes are different, Need to specify  contrail_internal_vip testbed.py."
        exit(1)
    elif len(env.roledefs['openstack']) == 0:
        print "\nINOF: \n\tNo Openstack nodes in env.roledefs. Assuming using external Openstack"
    else:
        print "\nINFO: \n\tOpenstack and cfgm nodes are same, No need for contrail_internal_vip to be specified in testbed.py."
    #  Check the cfgm/database nodes
    cfgm_nodes = deepcopy(env.roledefs['cfgm'])
    if (set(cfgm_nodes) != set(database_nodes) and
            set(database_nodes).issubset(set(cfgm_nodes))):
        print "\nERROR: \n\tcfgm and database nodes should be in,"
        print "\t 1.Different set of nodes or"
        print "\t 2.Same set of nodes or"
        print "\t 3.cfgm should be subset of database nodes."
        exit(1)
    if (env.roledefs['openstack'] and # Openstack defined
            [os_node for os_node in env.roledefs['openstack']
                if os_node in env.roledefs['all']] and # Openstack in all role(contrail-cloud deployment)
            keystone_ssl_enabled() and # ssl enabled for keystone
            not apiserver_ssl_enabled()): # ssl disabled for apiserver
        print "\nERROR: \n\tIn contrail cloud deployment, recommended to deploy both keystone and apiserver with ssl."
        exit(1)
    # Check for VIP's
    control_data = getattr(testbed, 'control_data', None)
    if (len(env.roledefs['openstack']) > 1 and control_data):
        if not get_openstack_internal_vip():
            print "\nERROR: \n\tMultiple openstack nodes, Specify 'internal_vip' and continue..."
        if not get_openstack_external_vip():
            print "\nERROR: \n\tMultiple openstack nodes with multi-interface, Specify 'external_vip' and continue..."
    elif (len(env.roledefs['openstack']) > 1 and not control_data):
        if not get_openstack_internal_vip():
            print "\nERROR: \n\tMultiple openstack nodes, Specify 'internal_vip' and continue..."
        if get_openstack_external_vip():
            print "\nERROR: \n\tNot a multi-interface setup, Remove 'external_vip' and continue..."
    if set(env.roledefs['openstack']) != set(env.roledefs['cfgm']):
        if (len(env.roledefs['cfgm']) > 1 and control_data):
            if not get_contrail_internal_vip():
                print "\nERROR: \n\tMultiple cfgm nodes, Specify 'contrail_internal_vip' and continue..."
            if not get_contrail_external_vip():
                print "\nERROR: \n\tMultiple cfgm nodes with multi-interface, Specify 'contrail_external_vip' and continue..."
        elif (len(env.roledefs['openstack']) > 1 and not control_data):
            if not get_contrail_internal_vip():
                print "\nERROR: \n\tMultiple cfgm nodes, Specify 'contrail_internal_vip' and continue..."
            if get_contrail_external_vip():
                print "\nERROR: \n\tNot a multi-interface setup, Remove 'contrail_external_vip' and continue..."


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
        if os_type in ['centos', 'centoslinux']:
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

@task
@EXECUTE_TASK
@roles('all')
def populate_hosts_file():
    execute("populate_hosts_file_node", env.host_string)

@task
def populate_hosts_file_node(*args):
    # Provisioning scripts require host names to add and remove 
    # nodes to a cluster. Add all the host names in the /etc/hosts file
    # if not already present.
    for host_string in args:
        with settings(host_string=host_string):
            host_name = sudo('hostname -s')
            ctrl_ip = hstr_to_ip(get_control_host_string(host_string))
        for every_host in env.roledefs['all']:
            with settings(host_string=every_host, warn_only=True):
                if sudo('grep %s /etc/hosts' % host_name).failed:
                     sudo("echo '%s     %s' >> /etc/hosts" % (ctrl_ip, host_name))

@task
@EXECUTE_TASK
@roles('all')
def setup_common():
    execute("setup_common_node", env.host_string)

@task
def setup_common_node(*args):
    for host_string in args:
        execute("setup_ntp_node", host_string)
        execute("populate_hosts_file_node", host_string)

@task
@roles('build')
def ssh_copy_id(id_file=None):
    if not getattr(env, 'password', None):
        raise RuntimeError("env.password not populated, please use:\n\t fab -I ssh_copy_id")
        return
    # Created temporary password file
    fd, fname = tempfile.mkstemp()
    with open(fname, 'w') as fd:
        fd.write(env.password)

    ssh_config = os.path.expanduser('~/.ssh/config')
    contrail_ssh_config = '%s.contrailbackup' % ssh_config
    # Bckup old ssh config file if exists.
    if os.path.isfile(ssh_config):
        os.rename(ssh_config, contrail_ssh_config)

    # Create ssh config with options to skip StrictHostKeyChecking
    config_lines = ['StrictHostKeyChecking no\n', 'UserKnownHostsFile=/dev/null']
    with open(ssh_config, 'w+') as fd:
        fd.writelines(config_lines)

    # Add the public keys to the nodes in cluster
    cmd = 'sshpass -f %s ssh-copy-id ' % fname
    if id_file:
        cmd += '-i %s ' % id_file
    for host_string in env.roledefs['all']:
        print "Copying key to %s" % host_string
        local('%s %s' % (cmd, host_string))
    # Restore the old ssh config file
    os.remove(ssh_config)
    if os.path.isfile(contrail_ssh_config):
        os.rename(contrail_ssh_config, ssh_config)
    # Remove temporary password file.
    os.remove(fname)

@roles('build')
@task
def purge_node(del_ctrl_ip):
    with settings(host_string=del_ctrl_ip):
        pkg_list = (
                    # Format
                    # Package_name, role, minimum nodes
                    ('contrail-control', 'control', 1),
                    ('contrail-config', 'cfgm', 1),
                    ('contrail-analytics', 'collector', 1),
                    ('contrail-openstack-database', 'database', 3),
                    ('contrail-openstack', 'openstack', 3),
                    ('contrail-web-core', 'webui', 1)
                   )
        del_role_list = []
        ctrl_node_dead = False

        if not ping_test(del_ctrl_ip):
            ctrl_node_dead = True
            print "The controller to be deleted %s is not reachable" % del_ctrl_ip
            print "We cannot completely remove configuration if the node is not reachable"
            print "DO NOT bring up the node up again if you chose to continue"

            if raw_input("Should we assume it is dead (Y/n): ") != "Y":
                print "Restore connectivity to %s to continue" % del_ctrl_ip
                return

        for host_string in env.roledefs['all']:
            if not ping_test(host_string):
                print "Node %s is not reachable" % host_string
                print "All the existing nodes in the cluster needs to be reachable to remove"
                print "a node from the cluster"
                print "Restore connectivity before continuing"
                return

        for pkg in pkg_list:
            if ctrl_node_dead:
                if raw_input("Remove %s in %s (Y/n): " % (pkg[1], del_ctrl_ip)) != 'Y':
                    continue
            else:
                # If the package is not installed or if it is 
                # there in the current testbed for the role then
                # dont mark it for removal.
                if not is_package_installed(pkg[0]) or \
                   del_ctrl_ip in env.roledefs[pkg[1]]:
                    continue

            if len(env.roledefs[pkg[1]]) < pkg[2]:
                raise SystemExit(del_ctrl_ip + " cannot be removed from role " + pkg[1] +
                                 " since it violates the minimum node requirement for the role")
            del_role_list.append(pkg[1])

    if len(del_role_list) == 0:
        print "Nothing to remove from the cluster. To remove the node from specific roles, modify roledefs in testbed.py"
        return

    print "****************************************************************"
    print " The following roles will be removed from ", del_ctrl_ip
    print del_role_list
    print "****************************************************************"

    if raw_input("Are you sure? (Y/n): ") == "Y":
        execute("purge_node_from_cluster", del_ctrl_ip, del_role_list)

@roles('build')
@task
def all_sm_reimage_status(attempts=180, interval=10, node=None, contrail_role='all', smgr_client=None):
    if smgr_client is None:
        sys.stdout.write('Please provide Server Manager Client absolute path as argument smgr_client\n')
        sys.exit(1)

    if node:
        nodes = node
    else:
        nodes = env.roledefs[contrail_role][:]
        esxi_hosts = getattr(testbed, 'esxi_hosts', None)
        if esxi_hosts:
            try:
                for k,v in esxi_hosts.items():
                    if 'contrail_vm' in v:#In vcenter gateway,contrail_vm not there
                        nodes.remove(v['contrail_vm']['host'])
            except Exception as e:
                print "%s"%e
                pass #Handing exception for vcenter gateway
                     #Entry for contrail_vm not there in testbed.py
        # Skip checking for nodes which are vms
        vm_nodes = getattr(testbed, 'vm_node_details', None)
        if vm_nodes:
            for vm_node in vm_nodes.keys():
                if vm_node in nodes:
                    nodes.remove(vm_node)

    count = 0
    node_status = {}
    node_status_save = {}
    for node in nodes:
        node_status_save[node]="initial_state"
    while count < int(attempts):
        sleep(int(interval))
        count+=1
        for node in nodes:
            if node_status_save[node] == "reimage_completed":
                continue
            user, hostip = node.split('@')
            cmd = smgr_client + " status server --ip %s" %(hostip)
            cmd = cmd + " | grep status"
            try:
                with settings(hide('running'), warn_only=True):
                    op_string=local(cmd,capture=True)
            except:
                node_status[node]=''
                time.sleep(2)
                continue
            if '\"reimage_failed\"' in op_string:
                node_status[node]="reimage_failed"
                sys.stdout.write('Reimage command FAILED\n')
                sys.stdout.write('%s :: %s\n' % (node, node_status[node]))
                sys.exit(1)
            elif '\"reimage_completed\"' in op_string:
                node_status[node]="reimage_completed"
            elif '\"reimage_started\"' in op_string:
                node_status[node]="reimage_started"
            elif '\"restart_issued\"' in op_string:
                node_status[node]="restart_issued"
            else:
                node_status[node]=''

        task_complete = 1
        for node in nodes:
            if node_status_save[node] == "reimage_completed":
                continue
            if node_status[node] != "reimage_completed":
                task_complete = 0
                if node_status[node] != "":
                    if node_status_save[node] != node_status[node]:
                        sys.stdout.write('%s :: %s -> %s\n' % (node, node_status_save[node], node_status[node]))
                        node_status_save[node]=node_status[node]
            else:
                if node_status_save[node] == 'initial_state':
                    #Handle cases where SM takes time to restart the nodes
                    task_complete = 0
                    sys.stdout.write('Waiting on SM to restart the node %s'%node)
                    continue
                node_status_save[node]=node_status[node]
                sys.stdout.write('%s :: %s -> %s\n' % (node, node_status_save[node], node_status[node]))

        if task_complete == 1:
            sys.stdout.write('Reimage Completed\n')
            return 0 #sys.exit(0)

    if count >= int(attempts):
        sys.stdout.write('Reimage FAILED\n')
        for node in nodes:
            if node_status[node] != "reimage_completed":
                sys.stdout.write('%s :: %s\n' % (node, node_status[node]))
        sys.exit(1)

#end all_sm_reimage_status

@task
def is_rpm_equal_or_higher(reference):
    """ Check if installed rpm is equal or higher than the given reference rpm info

        Argument:
        rpminfo - reference rpm info is accepted in two formats
            string: expected format "<epoch> <version> <release>"
            tuple: expected format ('<epoch>', '<version', '<release>')

        Verdict:
             True - if installed rpm is equal or higher version that the reference version
             False - if installed version is lower than the referece rpm
    """
    rpmlabel = 0
    if type(reference) is str:
        reference = tuple(reference.split())

    try:
        import rpm
        rpmlabel = 1
    except ImportError:
        from distutils.version import LooseVersion
        pass
    openstack_host = env.roledefs['openstack'][0]
    with settings(host_string=openstack_host,
                  password=get_env_passwords(openstack_host)):
        actual_version = sudo('rpm -q --qf \"%{epochnum} %{V} %{R}\" openstack-nova-api')
        actual_version = tuple(actual_version.split())
    if rpmlabel:
        if rpm.labelCompare(actual_version, reference) >= 0:
            return True
    elif LooseVersion(actual_version[0]) > LooseVersion(reference[0]) or \
         LooseVersion(actual_version[0]) == LooseVersion(reference[0]) and \
         LooseVersion(actual_version[1]) >= LooseVersion(reference[1]):
        return True
    else:
        return False

@task
def increase_vrouter_limit_node(*args):
    """Increase the maximum number of mpls label and nexthop on tsn node"""
    vrouter_module_params_dict = getattr(env, 'vrouter_module_params', None)
    if vrouter_module_params_dict:
        for host_string in args:
             if host_string in vrouter_module_params_dict:
                 if getattr(env, 'dpdk', None):
                     if host_string in env.dpdk:
                         dpdk_increase_vrouter_limit(host_string)
                 else:
                     cmd = "options vrouter"
                     cmd += " vr_mpls_labels=%s" % vrouter_module_params_dict[host_string].setdefault('mpls_labels', '5120')
                     cmd += " vr_nexthops=%s" % vrouter_module_params_dict[host_string].setdefault('nexthops', '65536')
                     cmd += " vr_vrfs=%s" % vrouter_module_params_dict[host_string].setdefault('vrfs', '5120')
                     cmd += " vr_bridge_entries=%s" % vrouter_module_params_dict[host_string].setdefault('macs', '262144')
                     cmd += " vr_flow_entries=%s" % vrouter_module_params_dict[host_string].setdefault('flow_entries', '524288')
                     with settings(host_string=host_string, warn_only=True):
                         sudo("echo %s > %s" %(cmd, '/etc/modprobe.d/vrouter.conf'))

# end increase_vrouter_limit_node

def dpdk_increase_vrouter_limit(host_string):
    """Increase the maximum number of mpls label and nexthop on tsn node"""
    vrouter_file = '/etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini'
    vrouter_module_params_dict = getattr(env, 'vrouter_module_params', None)
    cmd = "--vr_mpls_labels %s " % vrouter_module_params_dict[host_string].setdefault('mpls_labels', '5120')
    cmd += "--vr_nexthops %s " % vrouter_module_params_dict[host_string].setdefault('nexthops', '65536')
    cmd += "--vr_vrfs %s " % vrouter_module_params_dict[host_string].setdefault('vrfs', '5120')
    cmd += "--vr_bridge_entries %s " % vrouter_module_params_dict[host_string].setdefault('macs', '262144')
    cmd += "--vr_flow_entries %s " % vrouter_module_params_dict[host_string].setdefault('flow_entries', '524288')
    with settings(host_string=host_string, warn_only=True):
        sudo('sed -i \'s#\(^command=.*$\)#\\1 %s#\' %s' %(cmd, vrouter_file))
# end dpdk_increase_vrouter_limit

@task
@roles('all')
def cleanup_dockers():
    try:
        for host in env.roledefs["all"]:
            if host not in env.roledefs['compute']:
                print "Deleting all containers and docker images.."
                run('docker rm -f $(docker ps -a -q)')
                run('docker rmi $(docker images -q)')
    except Exception as e:
        print "%s"%e
        pass #Handling exception for vcenter
# end cleanup_dockers

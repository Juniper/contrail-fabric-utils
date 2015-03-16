import os
import re
import tempfile

from fabfile.config import *
from fabfile.templates import compute_vmx_template
from fabfile.tasks.install import yum_install, apt_install
from vcenter_prov import Vcenter as Vcenter
from fabfile.utils.cluster import get_orchestrator, ssh, execute_cmd_out
import logging as LOG
import paramiko
import socket

def configure_esxi_network(esxi_info):
    '''Provision ESXi server'''
    user = esxi_info['username']
    ip = esxi_info['ip']
    password = esxi_info['password']
    assert (user and ip and password), "User, password and IP of the ESXi server must be specified"

    orch = get_orchestrator()
    if orch == 'openstack': 
        vm_pg = esxi_info['vm_port_group']
        vm_switch = esxi_info['vm_vswitch']
        vm_switch_mtu = esxi_info['vm_vswitch_mtu']
    fabric_pg = esxi_info['fabric_port_group']
    fab_switch = esxi_info['fabric_vswitch']
    uplink_nic = esxi_info['uplink_nic']
    if orch == 'openstack':
        data_pg = esxi_info.get('data_port_group', None)
        data_switch = esxi_info.get('data_vswitch', None)
        data_nic = esxi_info.get('data_nic', None)

    host_string = '%s@%s' %(user, ip)
    with settings(host_string = host_string, password = password, 
                    warn_only = True, shell = '/bin/sh -l -c'):
        run('esxcli network vswitch standard add --vswitch-name=%s' %(fab_switch))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(fabric_pg, fab_switch))
        if uplink_nic:
            run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(uplink_nic, fab_switch))
        if orch == 'openstack':
            run('esxcli network vswitch standard add --vswitch-name=%s' %(vm_switch))
            run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(vm_pg, vm_switch))
            run('esxcli network vswitch standard set -v %s -m %s' % (vm_switch, vm_switch_mtu))
            run('esxcli network vswitch standard policy security set --vswitch-name=%s --allow-promiscuous=1' % (vm_switch))
            run('esxcli network vswitch standard portgroup set --portgroup-name=%s --vlan-id=4095' %(vm_pg))
            if data_switch:
                run('esxcli network vswitch standard add --vswitch-name=%s' %(data_switch))
            if data_nic:
                assert data_switch, "Data vSwitch must be specified to add data nic"
                run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(data_nic, data_switch))
            if data_pg:
                assert data_switch, "Data vSwitch must be specified to create data port group"
                run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(data_pg, data_switch))
#end configure_esxi_network

def create_vmx (esxi_host, vm_name):
    '''Creates vmx file for contrail compute VM (non vcenter env)'''
    fab_pg = esxi_host['fabric_port_group']
    vm_pg = esxi_host['vm_port_group']
    data_pg = esxi_host.get('data_port_group', None)
    orch = get_orchestrator()
    vm_name = vm_name
    vm_mac = esxi_host['contrail_vm']['mac']
    assert vm_mac, "MAC address for contrail-compute-vm must be specified"

    if orch is 'vcenter':
        ext_params = compute_vmx_template.vcenter_ext_template
    else:
        ext_params = compute_vmx_template.esxi_ext_template.safe_substitute({'__vm_pg__' : vm_pg})
      
    if data_pg:
        data_intf = compute_vmx_template.esxi_eth2_template.safe_substitute({'__data_pg__' : data_pg})
        ext_params += data_intf

    template_vals = { '__vm_name__' : vm_name,
                      '__vm_mac__' : vm_mac,
                      '__fab_pg__' : fab_pg,
                      '__extension_params__' : ext_params,
                    }
    _, vmx_file = tempfile.mkstemp(prefix=vm_name)
    _template_substitute_write(compute_vmx_template.template,
                               template_vals, vmx_file)
    print "VMX File %s created for VM %s" %(vmx_file, vm_name)
    return vmx_file
#end create_vmx

def update_compute_vm_settings(ip, user, passwd, name, ntp_server):
    MAX_RETRIES = 5
    retries = 0
    connected = False

    while retries <= MAX_RETRIES and connected == False:
        try:
            connected = True
            ssh_session = paramiko.SSHClient()
            ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            print "Connecting to ContrailVM ip:%s" %(ip)
            ssh_session.connect(ip, username=user, password=passwd, timeout=300)
        except socket.error, paramiko.SSHException:
             connected = False
             ssh_session.close()
             retries = retries + 1
             continue

    if retries > MAX_RETRIES:
            return ( "Connection to %s failed" % (ip))

    #Set up ntp  
    print "Updating NTP settings on ContrailVM"
    ntp_cmd = ('ntpdate "%s"') %(ntp_server)
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('mv /etc/ntp.conf /etc/ntp.conf.orig')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('touch /var/lib/ntp/drift')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('echo "driftfile /var/lib/ntp/drift" >> /etc/ntp.conf')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('echo "server %s" >> /etc/ntp.conf') % (ntp_server)
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('echo "restrict 127.0.0.1" >> /etc/ntp.conf')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('echo "restrict -6 ::1" >> /etc/ntp.conf')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    ntp_cmd = ('service ntp restart')
    out, err = execute_cmd_out(ssh_session, ntp_cmd)
    #end ntp setup

    #update /etc/hosts 
    etc_host_cmd = ('echo "%s %s" >> /etc/hosts') % (ip , name)
    out, err = execute_cmd_out(ssh_session, etc_host_cmd)

    # close ssh session
    ssh_session.close()
#end update_compute_vm_settings

def create_esxi_compute_vm (esxi_host, vcenter_info):
    '''Spawns contrail vm on openstack managed esxi server (non vcenter env)'''
    orch = get_orchestrator()
    datastore = esxi_host['datastore']
    vmdk = esxi_host['contrail_vm']['vmdk']
    if orch == 'openstack':
        assert vmdk, "Contrail VM vmdk image should be specified in testbed file"
    if orch ==  'vcenter':
        if vmdk is None:
            vmdk = esxi_host['contrail_vm']['vmdk_download_path'] 
            assert vmdk, "Contrail VM vmdk image or download path should be specified in testbed file"
    if orch is 'openstack':
        vm_name = esxi_host['contrail_vm']['name']
        vm_store = datastore + vm_name + '/'
    if orch is 'vcenter':
        name = "ContrailVM"
        vm_name = name+"-"+vcenter_info['datacenter']+"-"+esxi_host['ip']
        vm_store = datastore + '/' + vm_name + '/'

    vmx_file = create_vmx(esxi_host, vm_name)
    with settings(host_string = esxi_host['username'] + '@' + esxi_host['ip'],
                  password = esxi_host['password'], warn_only = True,
                  shell = '/bin/sh -l -c'):
         vmid = run("vim-cmd vmsvc/getallvms | grep %s | awk \'{print $1}\'" % vm_name)
         if vmid:
             run("vim-cmd vmsvc/power.off %s" % vmid)
             run("vim-cmd vmsvc/unregister %s" % vmid)

         run("rm -rf %s" % vm_store)
         out = run("mkdir -p %s" % vm_store)
         if out.failed:
             raise Exception("Unable create %s on esxi host %s:%s" % (vm_store,
                                     esxi_host['ip'], out))
         dst_vmx = vm_store + vm_name + '.vmx'
         out = put(vmx_file, dst_vmx)
         os.remove(vmx_file)
         if out.failed:
             raise Exception("Unable to copy %s to %s on %s:%s" % (vmx_file,
                                     vm_store, esxi_host['ip'], out))
         if orch == 'openstack':
             src_vmdk = '/var/tmp/%s' % os.path.split(vmdk)[-1]
         if orch == 'vcenter':
             src_vmdk = '/var/tmp/ContrailVM-disk1.vmdk'
         dst_vmdk = vm_store + vm_name + '.vmdk'
         put(vmdk, src_vmdk)
         out = run('vmkfstools -i "%s" -d zeroedthick "%s"' % (src_vmdk, dst_vmdk))
         if out.failed:
             raise Exception("Unable to create vmdk on %s:%s" %
                                      (esxi_host['ip'], out))
         run('rm ' + src_vmdk)
         out = run("vim-cmd solo/registervm " + dst_vmx)
         if out.failed:
             raise Exception("Unable to register VM %s on %s:%s" % (vm_name,
                                      esxi_host['ip'], out))
         out = run("vim-cmd vmsvc/power.on %s" % out)
         if out.failed:
             raise Exception("Unable to power on %s on %s:%s" % (vm_name,
                                      esxi_host['ip'], out))
    contrail_vm_info = esxi_host['contrail_vm']
    vm_host = contrail_vm_info['host'].split('@')
    vm_ip = vm_host[1]
    vm_user = vm_host[0]
    vm_passwd = env.passwords[contrail_vm_info['host']]
    ntp_server = contrail_vm_info['ntp_server']
    update_compute_vm_settings(vm_ip, vm_user, vm_passwd, name, ntp_server)
#end create_esxi_compute_vm

def _template_substitute(template, vals):
    data = template.safe_substitute(vals)
    return data
#end _template_substitute

def _template_substitute_write(template, vals, filename):
    data = _template_substitute(template, vals)
    outfile = open(filename, 'w')
    outfile.write(data)
    outfile.close()
#end _template_substitute_write

@task
def provision_vcenter(vcenter_info, hosts, vms):
        apt_install(['contrail-vmware-utils'])
        vcenter_params = {}
        vcenter_params['server'] = vcenter_info['server']
        vcenter_params['username'] = vcenter_info['username']
        vcenter_params['password'] = vcenter_info['password']

        vcenter_params['datacenter_name'] = vcenter_info['datacenter']
        vcenter_params['cluster_name'] = vcenter_info['cluster']
        vcenter_params['dvswitch_name'] = vcenter_info['dv_switch']['dv_switch_name']
        vcenter_params['dvportgroup_name'] = vcenter_info['dv_port_group']['dv_portgroup_name']
        vcenter_params['dvportgroup_num_ports'] = vcenter_info['dv_port_group']['number_of_ports']

        vcenter_params['hosts'] = hosts
        vcenter_params['vms'] = vms

        Vcenter(vcenter_params)
#end provision_vcenter

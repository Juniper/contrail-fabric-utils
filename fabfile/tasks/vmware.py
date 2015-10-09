import os
import re
import tempfile

from fabfile.config import *
from fabfile.templates import compute_vmx_template
from fabfile.tasks.install import yum_install, apt_install
from vcenter_prov import Vcenter as Vcenter
from vcenter_prov import cleanup_vcenter
from vcenter_prov import dvs_fab as dvs_fab
from vcenter_prov import vcenter_fab as vcenter_fab
from fabfile.utils.cluster import get_orchestrator, get_mode

def configure_esxi_network(esxi_info):
    '''Provision ESXi server'''
    user = esxi_info['username']
    ip = esxi_info['ip']
    password = esxi_info['password']
    assert (user and ip and password), "User, password and IP of the ESXi server must be specified"

    mode = get_mode(esxi_info['contrail_vm']['host'])
    if mode == 'openstack':
        vm_pg = esxi_info['vm_port_group']
        vm_switch = esxi_info['vm_vswitch']
        vm_switch_mtu = esxi_info['vm_vswitch_mtu']
        data_pg = esxi_info.get('data_port_group', None)
        data_switch = esxi_info.get('data_vswitch', None)
        data_nic = esxi_info.get('data_nic', None)
    fabric_pg = esxi_info['fabric_port_group']
    fab_switch = esxi_info['fabric_vswitch']
    uplink_nic = esxi_info['uplink_nic']

    host_string = '%s@%s' %(user, ip)
    with settings(host_string = host_string, password = password, 
                    warn_only = True, shell = '/bin/sh -l -c'):
        run('esxcli network vswitch standard add --vswitch-name=%s' %(fab_switch))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(fabric_pg, fab_switch))
        if uplink_nic:
            run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(uplink_nic, fab_switch))
        if mode == 'openstack':
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
    mode = get_mode(esxi_host['contrail_vm']['host'])
    vm_name = vm_name
    eth0_present = "TRUE"
    vm_mac = esxi_host['contrail_vm']['mac']
    assert vm_mac, "MAC address for contrail-compute-vm must be specified"

    if mode is 'vcenter':
        eth0_type = "vmxnet3"
        ext_params = compute_vmx_template.vcenter_ext_template
    else:
        eth0_type = "e1000"
        ext_params = compute_vmx_template.esxi_eth1_template.safe_substitute({'__vm_pg__' : vm_pg})

    if data_pg:
        data_intf = compute_vmx_template.esxi_eth2_template.safe_substitute({'__data_pg__' : data_pg})
        ext_params += data_intf
    if 'uplink' in esxi_host['contrail_vm'].keys():
        eth0_present = "FALSE"
    template_vals = { '__vm_name__' : vm_name,
                      '__vm_mac__' : vm_mac,
                      '__fab_pg__' : fab_pg,
                      '__eth0_type__' : eth0_type,
                      '__eth0_present__' : eth0_present,
                      '__extension_params__' : ext_params,
                    }
    _, vmx_file = tempfile.mkstemp(prefix=vm_name)
    _template_substitute_write(compute_vmx_template.template,
                               template_vals, vmx_file)
    print "VMX File %s created for VM %s" %(vmx_file, vm_name)
    return vmx_file
#end create_vmx

def create_esxi_compute_vm (esxi_host, vcenter_info, power_on):
    '''Spawns contrail vm on openstack managed esxi server (non vcenter env)'''
    mode = get_mode(esxi_host['contrail_vm']['host'])
    datastore = esxi_host['datastore']
    with settings(host_string = esxi_host['username'] + '@' + esxi_host['ip'],
                  password = esxi_host['password'], warn_only = True,
                  shell = '/bin/sh -l -c'):
        src_vmdk = "/var/tmp/ContrailVM-disk1.vmdk"
        if 'vmdk_download_path' in esxi_host['contrail_vm'].keys():
            vmdk_download_path = esxi_host['contrail_vm']['vmdk_download_path']
            run("wget -O %s %s" % (src_vmdk, vmdk_download_path))
        else:
            vmdk = esxi_host['contrail_vm']['vmdk']
            if vmdk is None:
                assert vmdk, "Contrail VM vmdk image or download path should be specified in testbed file"
            put(vmdk, src_vmdk)

        if mode is 'openstack':
            vm_name = esxi_host['contrail_vm']['name']
        if mode is 'vcenter':
            name = "ContrailVM"
            vm_name = name+"-"+vcenter_info['datacenter']+"-"+esxi_host['ip']
        vm_store = datastore + '/' + vm_name + '/'

        vmx_file = create_vmx(esxi_host, vm_name)
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
        dst_vmdk = vm_store + vm_name + '.vmdk'
        out = run('vmkfstools -i "%s" -d zeroedthick "%s"' % (src_vmdk, dst_vmdk))
        if out.failed:
            raise Exception("Unable to create vmdk on %s:%s" %
                                      (esxi_host['ip'], out))
        run('rm ' + src_vmdk)
        out = run("vim-cmd solo/registervm " + dst_vmx)
        if out.failed:
            raise Exception("Unable to register VM %s on %s:%s" % (vm_name,
                                      esxi_host['ip'], out))

        if (power_on == False):
            return

        out = run("vim-cmd vmsvc/power.on %s" % out)
        if out.failed:
            raise Exception("Unable to power on %s on %s:%s" % (vm_name,
                                      esxi_host['ip'], out))
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
def provision_vcenter_features(vcenter_info, esxi_info, host_list):
    apt_install(['contrail-vmware-utils'])
    vcenter_params = {}

    vcenter_params['vcenter_server'] = vcenter_info['server']
    vcenter_params['vcenter_username'] = vcenter_info['username']
    vcenter_params['vcenter_password'] = vcenter_info['password']

    vcenter_params['cluster_name'] = vcenter_info['cluster']
    vcenter_params['datacenter_name'] = vcenter_info['datacenter']

    vcenter_params['esxi_info'] = esxi_info
    vcenter_params['host_list'] = host_list

    vcenter_fab(vcenter_params)
#end provision_vcenter_features

@task
def provision_dvs_fab(vcenter_info, esxi_info, host_list):
    apt_install(['contrail-vmware-utils'])
    dvs_params = {}

    dvs_params['name'] = vcenter_info['dv_switch_fab']['dv_switch_name']
    dvs_params['dvportgroup_name'] = vcenter_info['dv_port_group_fab']['dv_portgroup_name']
    dvs_params['dvportgroup_num_ports'] = vcenter_info['dv_port_group_fab']['number_of_ports']
    dvs_params['dvportgroup_uplink'] = vcenter_info['dv_port_group_fab']['uplink']

    dvs_params['vcenter_server'] = vcenter_info['server']
    dvs_params['vcenter_username'] = vcenter_info['username']
    dvs_params['vcenter_password'] = vcenter_info['password']

    dvs_params['cluster_name'] = vcenter_info['cluster']
    dvs_params['datacenter_name'] = vcenter_info['datacenter']

    dvs_params['esxi_info'] = esxi_info
    dvs_params['host_list'] = host_list

    dvs_fab(dvs_params)
#end provision_dvs_fab

@task
def deprovision_vcenter(vcenter_info):
    apt_install(['contrail-vmware-utils'])
    cleanup_vcenter(vcenter_info)

@task
def provision_vcenter(vcenter_info, hosts, clusters, vms, update_dvs):
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
        vcenter_params['clusters'] = clusters
        vcenter_params['update_dvs'] = update_dvs

        Vcenter(vcenter_params)
#end provision_vcenter

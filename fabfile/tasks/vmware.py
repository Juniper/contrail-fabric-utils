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
from vcenter_prov import pci_fab as pci_fab
from vcenter_prov import sr_iov_fab as sr_iov_fab
from fabfile.utils.cluster import get_mode, get_vcenter_datacenter_mtu
from fabfile.utils.install import get_setup_vcenter_pkg

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
    datacenter_mtu = esxi_info.get('datacenter_mtu', None)

    host_string = '%s@%s' %(user, ip)
    with settings(host_string = host_string, password = password, 
                    warn_only = True, shell = '/bin/sh -l -c'):
        run('esxcli network vswitch standard add --vswitch-name=%s' %(fab_switch))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(fabric_pg, fab_switch))
        if uplink_nic:
            run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(uplink_nic, fab_switch))
        if datacenter_mtu:
            run('esxcli network vswitch standard set -v %s -m %s' % (fab_switch, datacenter_mtu))
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
    vm_mac = esxi_host['contrail_vm']['mac']
    assert vm_mac, "MAC address for contrail-compute-vm must be specified"

    cmd = "vmware -v"
    out = run(cmd)
    if out.failed:
        raise Exception("Unable to get the vmware version")
    esxi_version_info = str(out)
    esxi_version = esxi_version_info.split()[2][:3]
    version = float(esxi_version)
    if (version == 5.5):
         hw_version = 10
    elif (version >= 6.0):
         hw_version = 11
    else:
        hw_version = 9

    if mode is 'vcenter':
        eth0_type = "vmxnet3"
        ext_params = compute_vmx_template.vcenter_ext_template
    else:
        eth0_type = "e1000"
        ext_params = compute_vmx_template.esxi_eth1_template.safe_substitute({'__vm_pg__' : vm_pg})

    if data_pg:
        data_intf = compute_vmx_template.esxi_eth2_template.safe_substitute({'__data_pg__' : data_pg})
        ext_params += data_intf

    template_vals = { '__vm_name__' : vm_name,
                      '__hw_version__' : hw_version,
                      '__vm_mac__' : vm_mac,
                      '__fab_pg__' : fab_pg,
                      '__eth0_type__' : eth0_type,
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
            vm_name = name+"-"+esxi_host['datacenter']+"-"+esxi_host['ip']
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
def provision_vcenter_features(vcenter_info, esxi_info, host_list, datacenter, clusters):
    pkgs = get_setup_vcenter_pkg()
    apt_install(pkgs)
    vcenter_params = {}

    vcenter_params['vcenter_server'] = vcenter_info['server']
    vcenter_params['vcenter_username'] = vcenter_info['username']
    vcenter_params['vcenter_password'] = vcenter_info['password']

    vcenter_params['datacenter_name'] = datacenter
    vcenter_params['cluster_name'] = clusters

    vcenter_params['esxi_info'] = esxi_info
    vcenter_params['host_list'] = host_list

    vcenter_fab(vcenter_params)
#end provision_vcenter_features

@task
def provision_dvs_fab(vcenter_info, esxi_info, host_list):
    pkgs = get_setup_vcenter_pkg()
    apt_install(pkgs)
    dvs_params = {}

    for dc in vcenter_info['datacenters']:
        dc_info = vcenter_info['datacenters'][dc]
        for dvs in dc_info['dv_switches']:
            if dvs == 'dv_switch_fab':
               dv_switch_fab = dc_info['dv_switches'][dvs]
               break
        break

    dvs_params['name'] = dv_switch_fab['dv_switch_name']
    dvs_params['dvportgroup_name'] = dv_switch_fab['dv_port_group_fab']['dv_portgroup_name']
    dvs_params['dvportgroup_num_ports'] = dv_switch_fab['dv_port_group_fab']['number_of_ports']
    dvs_params['dvportgroup_uplink'] = dv_switch_fab['dv_port_group_fab']['uplink']
    dvs_params['datacenter_mtu'] = get_vcenter_datacenter_mtu(vcenter_info)

    dvs_params['vcenter_server'] = vcenter_info['server']
    dvs_params['vcenter_username'] = vcenter_info['username']
    dvs_params['vcenter_password'] = vcenter_info['password']

    dvs_params['cluster_name'] = esxi_info['cluster']
    dvs_params['datacenter_name'] = esxi_info['datacenter']

    dvs_params['esxi_info'] = esxi_info
    dvs_params['host_list'] = host_list

    dvs_fab(dvs_params)
#end provision_dvs_fab

@task
def provision_pci_fab(vcenter_info, esxi_info, host_list):
    pkgs = get_setup_vcenter_pkg()
    apt_install(pkgs)
    pci_params = {}

    pci_params['vcenter_server'] = vcenter_info['server']
    pci_params['vcenter_username'] = vcenter_info['username']
    pci_params['vcenter_password'] = vcenter_info['password']

    pci_params['cluster_name'] = esxi_info['cluster']
    pci_params['datacenter_name'] = esxi_info['datacenter']

    pci_params['esxi_info'] = esxi_info
    pci_params['host_list'] = host_list

    pci_fab(pci_params)
#end provision_pci_fab

@task
def provision_sr_iov_fab(vcenter_info, esxi_info, host_list):
    pkgs = get_setup_vcenter_pkg()
    apt_install(pkgs)
    sr_iov_params = {}

    sr_iov_params['dvs_name'] = vcenter_info['dv_switch_sr_iov']['dv_switch_name']
    sr_iov_params['dvportgroup_name'] = vcenter_info['dv_port_group_sr_iov']['dv_portgroup_name']
    sr_iov_params['dvportgroup_num_ports'] = vcenter_info['dv_port_group_sr_iov']['number_of_ports']

    sr_iov_params['vcenter_server'] = vcenter_info['server']
    sr_iov_params['vcenter_username'] = vcenter_info['username']
    sr_iov_params['vcenter_password'] = vcenter_info['password']

    sr_iov_params['cluster_name'] = esxi_info['cluster']
    sr_iov_params['datacenter_name'] = esxi_info['datacenter']
    sr_iov_params['datacenter_mtu'] = get_vcenter_datacenter_mtu(vcenter_info)

    sr_iov_params['esxi_info'] = esxi_info
    sr_iov_params['host_list'] = host_list

    sr_iov_fab(sr_iov_params)
#end provision_sr_iov_fab

@task
def deprovision_vcenter(vcenter_info, datacenter):
    cleanup_vcenter(vcenter_info, datacenter)

@task
def provision_vcenter(vcenter_info, datacenter, datacenter_mtu, dv_switches, clusters, hosts, vms):
        pkgs = get_setup_vcenter_pkg()
        apt_install(pkgs)

        vcenter_params = {}
        vcenter_params['server'] = vcenter_info['server']
        vcenter_params['username'] = vcenter_info['username']
        vcenter_params['password'] = vcenter_info['password']

        vcenter_params['datacenter_name'] = datacenter
        vcenter_params['datacenter_mtu'] = datacenter_mtu
        vcenter_params['dv_switches'] = dv_switches
        vcenter_params['clusters'] = clusters
        vcenter_params['hosts'] = hosts
        vcenter_params['vms'] = vms

        Vcenter(vcenter_params)
#end provision_vcenter

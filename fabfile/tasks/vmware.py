import os
import re
import tempfile

from fabfile.config import *
from fabfile.templates import compute_vmx_template
from fabfile.tasks.install import yum_install, apt_install
from esxi_prov import ContrailVM as ContrailVM
from vcenter_prov import Vcenter as Vcenter

def configure_esxi_network(esxi_info):
    '''Provision ESXi server'''
    user = esxi_info['username']
    password = esxi_info['password']
    ip = esxi_info['ip']
    assert (user and ip and password), "User, password and IP of the ESXi server must be specified"
    
    vm_pg = esxi_info['vm_port_group']
    fabric_pg = esxi_info['fabric_port_group']
    fab_switch = esxi_info['fabric_vswitch']
    vm_switch = esxi_info['vm_vswitch']
    vm_switch_mtu = esxi_info['vm_vswitch_mtu']
    uplink_nic = esxi_info['uplink_nic']
    data_pg = esxi_info.get('data_port_group', None)
    data_switch = esxi_info.get('data_vswitch', None)
    data_nic = esxi_info.get('data_nic', None)

    host_string = '%s@%s' %(user, ip)
    with settings(host_string = host_string, password = password, 
                    warn_only = True, shell = '/bin/sh -l -c'):
        run('esxcli network vswitch standard add --vswitch-name=%s' %(vm_switch))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(vm_pg, vm_switch))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(fabric_pg, fab_switch))
        run('esxcli network vswitch standard set -v %s -m %s' % (vm_switch, vm_switch_mtu))
        run('esxcli network vswitch standard policy security set --vswitch-name=%s --allow-promiscuous=1' % (vm_switch))
        run('esxcli network vswitch standard portgroup set --portgroup-name=%s --vlan-id=4095' %(vm_pg))
        if uplink_nic:
            run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(uplink_nic, fab_switch))
        if data_switch:
            run('esxcli network vswitch standard add --vswitch-name=%s' %(data_switch))
        if data_nic:
            assert data_switch, "Data vSwitch must be specified to add data nic"
            run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(data_nic, data_switch))
        if data_pg:
            assert data_switch, "Data vSwitch must be specified to create data port group"
            run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(data_pg, data_switch))


def create_vmx (esxi_host):
    '''Creates vmx file for contrail compute VM (non vcenter env)'''
    fab_pg = esxi_host['fabric_port_group']
    vm_pg = esxi_host['vm_port_group']
    data_pg = esxi_host.get('data_port_group', None)
    vm_name = esxi_host['contrail_vm']['name']
    vm_mac = esxi_host['contrail_vm']['mac']
    assert vm_mac, "MAC address for contrail-compute-vm must be specified"

    ext_params = compute_vmx_template.esxi_eth1_template.safe_substitute({'__vm_pg__' : vm_pg})
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

def create_esxi_compute_vm (esxi_host):
    '''Spawns contrail vm on openstack managed esxi server (non vcenter env)'''
    vmx_file = create_vmx(esxi_host)
    datastore = esxi_host['datastore']
    vmdk = esxi_host['contrail_vm']['vmdk']
    assert vmdk, "Contrail VM vmdk image should be specified in testbed file"
    vm_name = esxi_host['contrail_vm']['name']
    vm_store = datastore + vm_name + '/'

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
         src_vmdk = '/var/tmp/%s' % os.path.split(vmdk)[-1]
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
def provision_vcenter(vcenter_info, esxi_info):
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
        hosts = []
        vms = []
        for host in esxi_info.keys():
                esxi_data = esxi_info[host]
                data = esxi_data['esxi']

                esx_list=[data['esx_ip'],data['esx_username'],data['esx_password'],data['esx_ssl_thumbprint']]
                hosts.append(esx_list)
                modified_vm_name = esxi_data['esx_vm_name']+"-"+vcenter_info['datacenter']+"-"+esxi_data['contrailvm_ip']
                vms.append(modified_vm_name)

        vcenter_params['hosts'] = hosts
        vcenter_params['vms'] = vms

        Vcenter(vcenter_params)


@task
def provision_esxi(deb, vcenter_info, compute_vm_info):
            vm_params = {}
            modified_vm_name = compute_vm_info['esx_vm_name']+"-"+vcenter_info['datacenter']+"-"+compute_vm_info['contrailvm_ip']
            vm_params['vm'] = modified_vm_name
            vm_params['vmdk'] = "ContrailVM-disk1"
            vm_params['datastore'] = compute_vm_info['esx_datastore']
            vm_params['eth0_mac'] = compute_vm_info['contrailvm_virtual_mac']
            vm_params['eth0_ip'] = compute_vm_info['contrailvm_ip']
            vm_params['eth0_pg'] = compute_vm_info['esxi']['esx_fab_port_group']
            vm_params['eth0_vswitch'] = compute_vm_info['esxi']['esx_fab_vswitch']
            vm_params['eth0_vlan'] = None
            vm_params['uplink_nic'] = compute_vm_info['esxi']['esx_uplink_nic']
            vm_params['uplink_vswitch'] = compute_vm_info['esxi']['esx_fab_vswitch']
            vm_params['server'] = compute_vm_info['esxi']['esx_ip']
            vm_params['username'] = compute_vm_info['esxi']['esx_username']
            vm_params['password'] = compute_vm_info['esxi']['esx_password']
            if 'esx_vmdk' not in compute_vm_info.keys():
                vm_params['thindisk'] =  None
                print 'esx_vmdk, which is local vmdk path not found, expecting vmdk_download_path in testbed'
                if 'vmdk_download_path' not in compute_vm_info.keys():
                    print 'No vmdk_download_path specified. Cannot proceed further'
                    return
                print 'Found vmdk_download_path in testbed.py, proceeding further...'
                vm_params['vmdk_download_path'] =  compute_vm_info['vmdk_download_path']
            else:
                vm_params['thindisk'] =  compute_vm_info['esx_vmdk']
                vm_params['vmdk_download_path'] = None
            vm_params['domain'] =  compute_vm_info['domain']
            vm_params['vm_password'] = compute_vm_info['password']
            vm_params['vm_server'] = compute_vm_info['esx_vm_name']
            vm_params['ntp_server'] = compute_vm_info['esx_ntp_server']
            if deb is not None:
                vm_params['vm_deb'] = deb
            else:
                print 'deb package not passed as param, expecting in testbed'
                if 'vm_deb' not in compute_vm_info.keys():
                    print 'No deb package section in testbed.py. Exiting!'
                    return
                vm_params['vm_deb'] = compute_vm_info['vm_deb']
            out = ContrailVM(vm_params)
            print out




                                  

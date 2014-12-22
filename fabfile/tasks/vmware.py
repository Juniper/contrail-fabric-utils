import os
import re

from fabfile.config import *
from fabfile.templates import compute_ovf_template, compute_vmx_template
from fabfile.tasks.install import yum_install, apt_install
from esxi_prov import ContrailVM as ContrailVM
from vcenter_prov import Vcenter as Vcenter

def _get_var(var, default=None):
    try:
        return var
    except Exception:
        return default
#end _get_var

def configure_esxi_network(esxi_info):
    #ESXI Host Login
    host_string = '%s@%s' %(esxi_info['username'],
                           esxi_info['ip'])
    password = _get_var(esxi_info['password'])
    
    compute_pg = _get_var(esxi_info['vm_port_group'],'compute_pg')
    fabric_pg = _get_var(esxi_info['fabric_port_group'],'fabric_pg')
    vswitch0 = _get_var(esxi_info['fabric_vswitch'],'vSwitch0')
    vswitch1 = _get_var(esxi_info['vm_vswitch'],'vSwitch1')
    uplink_nic = esxi_info['uplink_nic']
    with settings(host_string = host_string, password = password, 
                    warn_only = True, shell = '/bin/sh -l -c'):
        run('esxcli network vswitch standard add --vswitch-name=%s' %(
                vswitch1))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(compute_pg, vswitch1))
        run('esxcli network vswitch standard portgroup add --portgroup-name=%s --vswitch-name=%s' %(fabric_pg, vswitch0))
        run('esxcli network vswitch standard uplink add --uplink-name=%s --vswitch-name=%s' %(uplink_nic, vswitch0))
        run('esxcli network vswitch standard portgroup set --portgroup-name=%s --vlan-id=4095' %(compute_pg))

@task

def create_ovf(compute_vm_info):
    compute_vm_name = _get_var(compute_vm_info['vm_name'],'Fedora-Compute-VM')
    compute_vm_vmdk = compute_vm_info['vmdk']
#    compute_vm_vmdk = 'Fedora-Compute-VM1-disk1.vmdk'
    compute_pg = _get_var(compute_vm_info['port_group'],'compute_pg')
    fabric_pg = _get_var(compute_vm_info['esxi']['vm_port_group'],'fabric_pg')
    ovf_file = '%s.ovf' %(compute_vm_name)
    template_vals = {'__compute_vm_name__': compute_vm_name,
                     '__compute_vm_vmdk__': compute_vm_vmdk,
                     '__compute_pg__': compute_pg,
                     '__fabric_pg__': fabric_pg,
                    }
    _template_substitute_write(compute_ovf_template.template,
                               template_vals, ovf_file)
    ovf_file_path = os.path.realpath(ovf_file)
    print "\n\nOVF File %s created for VM %s" %(ovf_file_path, compute_vm_name)
#end create_ovf
    
def create_vmx (esxi_host):
    '''Creates vmx file for contrail compute VM (non vcenter env)'''
    fab_pg = esxi_host.get('fabric_port_group', 'fabric_pg')
    vm_pg = esxi_host.get('vm_port_group', 'compute_pg')
    vm_name = esxi_host['contrail_vm']['name']
    vm_mac = esxi_host['contrail_vm']['mac']
    template_vals = { '__vm_name__' : vm_name,
                      '__vm_mac__' : vm_mac,
                      '__fab_pg__' : fab_pg,
                      '__vm_pg__' : vm_pg,
                    }
    vmx_file = '%s.vmx' % vm_name
    _template_substitute_write(compute_vmx_template.template,
                               template_vals, vmx_file)
    print "VMX File %s created for VM %s" %(os.path.realpath(vmx_file), vm_name)
    return os.path.realpath(vmx_file)
#end create_vmx

def create_esxi_compute_vm (esxi_host):
    '''Spawns contrail vm on openstack managed esxi server (non vcenter env)'''
    vmx_file = create_vmx(esxi_host)
    datastore = esxi_host['contrail_vm'].get('datastore', '/vmfs/volumes/datastore1/')
    vmdk = esxi_host['contrail_vm'].get('vmdk', None)
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
         out = run("mkdir -p %s/vmware_base/" % datastore)
         if out.failed:
             raise Exception("Unable create vmware_base on esxi host %s:%s" % (
                                     esxi_host['ip'], out))
         out = put(vmx_file, vm_store)
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
         out = run("vim-cmd solo/registervm " + vm_store + os.path.split(vmx_file)[-1])
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
        vcenter_params['dvswitch_nic'] = vcenter_info['dv_switch']['nic']
        vcenter_params['dvportgroup_name'] = vcenter_info['dv_port_group']['dv_portgroup_name']
        vcenter_params['dvportgroup_num_ports'] = vcenter_info['dv_port_group']['number_of_ports']
        hosts = []
        for host in esxi_info.keys():
                esxi_data = esxi_info[host]
                data = esxi_data['esxi']

                esx_list=[data['esx_ip'],data['esx_username'],data['esx_password'],data['esx_ssl_thumbprint']]
                hosts.append(esx_list)

        vcenter_params['hosts'] = hosts

        Vcenter(vcenter_params)


@task
def provision_esxi(compute_vm_info):
            vm_params = {}
            vm_params['vm'] = compute_vm_info['esx_vm_name']
            vm_params['vmdk'] = _get_var(compute_vm_info['vmdk'])
            vm_params['datastore'] = compute_vm_info['esx_datastore']
            vm_params['eth0_mac'] = _get_var(compute_vm_info['server_mac'])
            vm_params['eth0_ip'] = _get_var(compute_vm_info['server_ip'])
            vm_params['eth0_pg'] = _get_var(compute_vm_info['esxi']['esx_fab_port_group'])
            vm_params['eth0_vswitch'] = _get_var(compute_vm_info['esxi']['esx_fab_vswitch'])
            vm_params['eth0_vlan'] = None
            vm_params['eth1_vswitch'] = _get_var(compute_vm_info['esx_vm_vswitch'])
            vm_params['eth1_pg'] = _get_var(compute_vm_info['esx_vm_port_group'])
            vm_params['eth1_vlan'] = "4095"
            vm_params['uplink_nic'] = _get_var(compute_vm_info['esxi']['esx_uplink_nic'])
            vm_params['uplink_vswitch'] = _get_var(compute_vm_info['esxi']['esx_fab_vswitch'])
            vm_params['server'] = _get_var(compute_vm_info['esxi']['esx_ip'])
            vm_params['username'] = _get_var(compute_vm_info['esxi']['esx_username'])
            vm_params['password'] = _get_var(compute_vm_info['esxi']['esx_password'])
            vm_params['thindisk'] =  _get_var(compute_vm_info['esx_vmdk'])
            vm_params['domain'] =  _get_var(compute_vm_info['domain'])
            vm_params['vm_password'] = _get_var(compute_vm_info['password'])
            vm_params['vm_server'] = _get_var(compute_vm_info['server_id'])
            vm_params['vm_deb'] = _get_var(compute_vm_info['vm_deb'])
            out = ContrailVM(vm_params)
            print out




                                  

import os
import re

from fabfile.config import *
from fabfile.templates import compute_ovf_template
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
        vms = []
        for host in esxi_info.keys():
                esxi_data = esxi_info[host]
                data = esxi_data['esxi']

                esx_list=[data['esx_ip'],data['esx_username'],data['esx_password'],data['esx_ssl_thumbprint']]
                hosts.append(esx_list)
                vms.append(esxi_data['esx_vm_name'])

        vcenter_params['hosts'] = hosts
        vcenter_params['vms'] = vms

        Vcenter(vcenter_params)


@task
def provision_esxi(deb, compute_vm_info):
            vm_params = {}
            vm_params['vm'] = compute_vm_info['esx_vm_name']
            vm_params['vmdk'] = _get_var(compute_vm_info['vmdk'])
            vm_params['datastore'] = compute_vm_info['esx_datastore']
            vm_params['eth0_mac'] = _get_var(compute_vm_info['server_mac'])
            vm_params['eth0_ip'] = _get_var(compute_vm_info['server_ip'])
            vm_params['eth0_pg'] = _get_var(compute_vm_info['esxi']['esx_fab_port_group'])
            vm_params['eth0_vswitch'] = _get_var(compute_vm_info['esxi']['esx_fab_vswitch'])
            vm_params['eth0_vlan'] = None
            vm_params['uplink_nic'] = _get_var(compute_vm_info['esxi']['esx_uplink_nic'])
            vm_params['uplink_vswitch'] = _get_var(compute_vm_info['esxi']['esx_fab_vswitch'])
            vm_params['server'] = _get_var(compute_vm_info['esxi']['esx_ip'])
            vm_params['username'] = _get_var(compute_vm_info['esxi']['esx_username'])
            vm_params['password'] = _get_var(compute_vm_info['esxi']['esx_password'])
            if 'esx_vmdk' not in compute_vm_info.keys():
                vm_params['thindisk'] =  None
                print 'esx_vmdk, which is local vmdk path not found, expecting vmdk_download_path in testbed'
                if 'vmdk_download_path' not in compute_vm_info.keys():
                    print 'No vmdk_download_path specified. Cannot proceed further'
                    return
                print 'Found vmdk_download_path in testbed.py, proceeding further...'
                vm_params['vmdk_download_path'] =  _get_var(compute_vm_info['vmdk_download_path'])
            else:
                vm_params['thindisk'] =  _get_var(compute_vm_info['esx_vmdk'])
            vm_params['domain'] =  _get_var(compute_vm_info['domain'])
            vm_params['vm_password'] = _get_var(compute_vm_info['password'])
            vm_params['vm_server'] = _get_var(compute_vm_info['server_id'])
            vm_params['ntp_server'] = _get_var(compute_vm_info['esx_ntp_server'])
            if deb is not None:
                vm_params['vm_deb'] = deb
            else:
                print 'deb package not passed as param, expecting in testbed'
                if 'vm_deb' not in compute_vm_info.keys():
                    print 'No deb package section in testbed.py. Exiting!'
                    return
                vm_params['vm_deb'] = _get_var(compute_vm_info['vm_deb'])
            out = ContrailVM(vm_params)
            print out




                                  

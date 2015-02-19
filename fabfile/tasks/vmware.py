import os
import re
import tempfile

from fabfile.config import *
from fabfile.templates import compute_vmx_template
from fabfile.tasks.install import yum_install, apt_install
from esxi_prov import ContrailVM as ContrailVM, ssh, execute_cmd_out
from vcenter_prov import Vcenter as Vcenter

def configure_esxi_network(esxi_info):
    '''Provision ESXi server'''
    user = esxi_info['username']
    ip = esxi_info['ip']
    password = esxi_info['password']
    assert (user and ip and password), "User, password and IP of the ESXi server must be specified"

    vm_pg = esxi_info['vm_port_group']
    fabric_pg = esxi_info['fabric_port_group']
    fab_switch = esxi_info['fabric_vswitch']
    vm_switch = esxi_info['vm_vswitch']
    vm_switch_mtu = esxi_info['vm_vswitch_mtu']
    uplink_nic = esxi_info['uplink_nic']

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


def create_vmx (esxi_host):
    '''Creates vmx file for contrail compute VM (non vcenter env)'''
    fab_pg = esxi_host['fabric_port_group']
    vm_pg = esxi_host['vm_port_group']
    vm_name = esxi_host['contrail_vm']['name']
    vm_mac = esxi_host['contrail_vm']['mac']
    assert vm_mac, "MAC address for contrail-compute-vm must be specified"

    template_vals = { '__vm_name__' : vm_name,
                      '__vm_mac__' : vm_mac,
                      '__fab_pg__' : fab_pg,
                      '__vm_pg__' : vm_pg,
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

                vm_name = "ContrailVM"

                ssh_session = ssh(esxi_data['ip'], esxi_data['username'], esxi_data['password'])
                get_ssl_thumbprint = ("openssl x509 -in /etc/vmware/ssl/rui.crt -fingerprint -sha1 -noout")
                out, err = execute_cmd_out(ssh_session, get_ssl_thumbprint)
                out = out.split()
                out = out[1].split('=')
                ssl_thumbprint = out[1]
                print 'ssl thumbprint of the ESXi host %s is %s' % (esxi_data['ip'], ssl_thumbprint)

                esx_list=esxi_data['ip'],esxi_data['username'],esxi_data['password'],ssl_thumbprint
                hosts.append(esx_list)
                modified_vm_name = vm_name+"-"+vcenter_info['datacenter']+"-"+esxi_data['ip']
                vms.append(modified_vm_name)

        vcenter_params['hosts'] = hosts
        vcenter_params['vms'] = vms

        Vcenter(vcenter_params)

@task
def provision_esxi_node(deb, vcenter_info, esxi_info, compute_vm_info):
            vm_params = {}

            host = compute_vm_info['host'].split('@')
            vm_ip = host[1]

            vm_name = "ContrailVM"
            modified_vm_name = vm_name+"-"+vcenter_info['datacenter']+"-"+esxi_info['ip']
            vm_params['vm'] = modified_vm_name
            vm_params['vmdk'] = "ContrailVM-disk1"
            vm_params['datastore'] = esxi_info['datastore']
            vm_params['eth0_mac'] = compute_vm_info['mac']
            vm_params['eth0_ip'] = vm_ip
            vm_params['eth0_pg'] = esxi_info['fabric_port_group']
            vm_params['eth0_vswitch'] = esxi_info['fabric_vswitch']
            vm_params['eth0_vlan'] = None
            vm_params['uplink_nic'] = esxi_info['uplink_nic']
            vm_params['uplink_vswitch'] = esxi_info['fabric_vswitch']
            vm_params['server'] = esxi_info['ip']
            vm_params['username'] = esxi_info['username']
            vm_params['password'] = esxi_info['password']
            if 'vmdk_download_path' not in compute_vm_info.keys():
                vm_params['vmdk_download_path'] = None
                print 'vmdk_download_path is not found, expecting vmdk in testbed'
                if compute_vm_info['vmdk'] is None:
                    print 'No vmdk specified. Cannot proceed further'
                    return
                else:
                    print 'Found vmdk specified in testbed...'
                    vm_params['thindisk'] = compute_vm_info['vmdk']
            else:
                vm_params['thindisk'] = None 
                print 'Found vmdk_download_path in testbed.py, proceeding further...'
                vm_params['vmdk_download_path'] = compute_vm_info['vmdk_download_path'] 
                print 'vmdk_download_path is %s' % vm_params['vmdk_download_path']
            vm_params['vm_password'] = (env.passwords[compute_vm_info['host']])
            vm_params['vm_server'] = vm_name
            vm_params['ntp_server'] = compute_vm_info['ntp_server']
            if deb is not None:
                vm_params['vm_deb'] = deb
            else:
                print 'deb package not passed as param, expecting in testbed.py'
                if 'deb' not in compute_vm_info.keys():
                    print 'No deb package section in testbed.py. Exiting!'
                    return
                vm_params['vm_deb'] = compute_vm_info['deb']
            out = ContrailVM(vm_params)
            print out

import os
import re

from fabfile.config import *
from fabfile.templates import compute_ovf_template
from fabfile.templates import compute_vmx_template

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

def create_compute_vm (esxi_host):
    vmx_file = create_vmx(esxi_host)
    datastore = esxi_host['contrail_vm'].get('datastore', '/vmfs/volumes/datastore1/')
    vmdk = esxi_host['contrail_vm'].get('image', '/images/ContrailVM-disk1.vmdk')
    vm_name = esxi_host['contrail_vm']['name']
    vm_store = datastore + vm_name + '/'
    img_server = '10.204.216.51' if '10.204' in esxi_host['ip'] else '10.84.5.100'

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
         out = put(vmx_file, vm_store)
         if out.failed:
             raise Exception("Unable to copy %s to %s on %s:%s" % (vmx_file,
                                     vm_store, esxi_host['ip'], out))
         run("cd /var/tmp/; wget http://%s/%s" % (img_server, vmdk))
         src_vmdk = '/var/tmp/%s' % os.path.split(vmdk)[-1]
         dst_vmdk = vm_store + vm_name + '.vmdk'
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
#end create_compute_vm

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

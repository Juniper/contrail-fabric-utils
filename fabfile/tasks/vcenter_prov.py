"""
Python program for provisioning vcenter 
"""

import atexit
import time

class Vcenter(object):
    def __init__(self, vcenter_params):
	self.pyVmomi =  __import__("pyVmomi")
        self.server = vcenter_params['server']
        self.username = vcenter_params['username']
        self.password = vcenter_params['password']
        self.datacenter_name = vcenter_params['datacenter_name']
        self.cluster_name = vcenter_params['cluster_name']
        self.dvswitch_name = vcenter_params['dvswitch_name']
        self.dvportgroup_name = vcenter_params['dvportgroup_name']
        self.dvportgroup_num_ports = vcenter_params['dvportgroup_num_ports']
        self.hosts = vcenter_params['hosts']
        self.vms = vcenter_params['vms']
        
        try:
            
            self.connect_to_vcenter() 
            datacenter = self.create_datacenter(dcname=self.datacenter_name)
            cluster=self.create_cluster(self.cluster_name,datacenter)
            network_folder = datacenter.networkFolder
	    for host_info in self.hosts:
            	self.add_host(cluster,host_info[0],host_info[3],host_info[1],host_info[2])
            dvs=self.create_dvSwitch(self.service_instance, network_folder, cluster, self.dvswitch_name)
            self.add_dvPort_group(self.service_instance,dvs, self.dvportgroup_name)
            for vm_name in self.vms:
                self.add_vm_to_dvpg(self.service_instance,vm_name,dvs, self.dvportgroup_name)
            
        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return 
        

    def create_cluster(self, cluster_name, datacenter):
        
        cluster = self.get_obj([self.pyVmomi.vim.ClusterComputeResource], cluster_name)
        if cluster is not None:
            print("cluster already exists")
            return cluster
            
        else:
            if cluster_name is None:
                raise ValueError("Missing value for name.")
            if datacenter is None:
                raise ValueError("Missing value for datacenter.")
            
            cluster_spec = self.pyVmomi.vim.cluster.ConfigSpecEx()
        
            host_folder = datacenter.hostFolder
            cluster = host_folder.CreateClusterEx(name=cluster_name, spec=cluster_spec)
            return cluster

    def add_host(self, cluster, hostname, sslthumbprint, username, password):
        host = self.get_obj([self.pyVmomi.vim.HostSystem], hostname)
        if host is not None:
            print("host already exists") 
            return host
        else:
            if hostname is None:
                raise ValueError("Missing value for name.")
            if cluster is None:
                raise ValueError("Missing value for cluster.")
            try:
                #openssl x509 -in /etc/vmware/ssl/rui.crt -fingerprint -sha1 -noout
                hostspec = self.pyVmomi.vim.host.ConnectSpec(hostName=hostname,sslThumbprint=sslthumbprint,userName=username, password=password)
                
                task=cluster.AddHost_Task(spec=hostspec,asConnected=True)
                
            except self.pyVmomi.vmodl.MethodFault as error:
                print "Caught vmodl fault : " + error.msg
                return -1
            #host = self.pyVmomi.vim.ClusterComputeResource.AddHost(hostspec)
        
            #host_folder = datacenter.hostFolder
            #cluster = host_folder.CreateClusterEx(name=cluster_name, spec=cluster_spec)
            self.wait_for_task(task, self.service_instance)
            host = self.get_obj([self.pyVmomi.vim.HostSystem], hostname)
            return host

    def create_vswitch(self, host_network_system, virt_sw_name, num_ports, nic_name):
        virt_sw_spec = self.pyVmomi.vim.host.VirtualSwitch.Specification()
        virt_sw_spec.numPorts = num_ports
        #vss_spec.bridge = self.pyVmomi.vim.host.VirtualSwitch.SimpleBridge(nicDevice='pnic_key')
        virt_sw_spec.bridge = self.pyVmomi.vim.host.VirtualSwitch.BondBridge(nicDevice=[nic_name])
        host_network_system.AddVirtualSwitch(vswitchName=virt_sw_name, spec=virt_sw_spec)
        print "Successfully created vSwitch ", virt_sw_name
    
    def add_virtual_nic(self, host_network_system, pg_name):
        vnic_spec = self.pyVmomi.vim.host.VirtualNic.Specification()
        vnic_spec.ip = self.pyVmomi.vim.host.IpConfig(dhcp=True)
        vnic_spec.mac = '00:50:56:7d:5e:0b'
        #host_network_system.AddServiceConsoleVirtualNic(portgroup=pg_name, nic=vnic_spec)
        host_network_system.AddVirtualNic(portgroup=pg_name, nic=vnic_spec)
    
    def create_port_group(self, host_network_system, pg_name, virt_sw_name):
        port_group_spec = self.pyVmomi.vim.host.PortGroup.Specification()
        port_group_spec.name = pg_name
        port_group_spec.vlanId = 0
        port_group_spec.vswitchName = virt_sw_name
        security_policy = self.pyVmomi.vim.host.NetworkPolicy.SecurityPolicy()
        security_policy.allowPromiscuous = True
        security_policy.forgedTransmits = True
        security_policy.macChanges = False
        port_group_spec.policy = self.pyVmomi.vim.host.NetworkPolicy(security=security_policy)
        host_network_system.AddPortGroup(portgrp=port_group_spec)
        print "Successfully created PortGroup ", pg_name
    
    def add_dvPort_group(self, si,dv_switch, dv_port_name):
        dv_pg = self.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
        if dv_pg is not None:
            print("dv port group already exists")
            return dv_pg
        else:
            dv_pg_spec = self.pyVmomi.vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
            dv_pg_spec.name = dv_port_name
            dv_pg_spec.numPorts = int(self.dvportgroup_num_ports)
            dv_pg_spec.type = self.pyVmomi.vim.dvs.DistributedVirtualPortgroup.PortgroupType.earlyBinding
            dv_pg_spec.defaultPortConfig = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
            dv_pg_spec.defaultPortConfig.securityPolicy = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.SecurityPolicy()
            dv_pg_spec.defaultPortConfig.vlan = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.TrunkVlanSpec()
            dv_pg_spec.defaultPortConfig.vlan.vlanId = [self.pyVmomi.vim.NumericRange(start=1, end=4094)]
            dv_pg_spec.defaultPortConfig.securityPolicy.allowPromiscuous = self.pyVmomi.vim.BoolPolicy(value=True)
            dv_pg_spec.defaultPortConfig.securityPolicy.forgedTransmits = self.pyVmomi.vim.BoolPolicy(value=True)
            dv_pg_spec.defaultPortConfig.vlan.inherited = False
            dv_pg_spec.defaultPortConfig.securityPolicy.macChanges = self.pyVmomi.vim.BoolPolicy(value=False)
            dv_pg_spec.defaultPortConfig.securityPolicy.inherited = False
            task=dv_switch.AddDVPortgroup_Task([dv_pg_spec])
            self.wait_for_task(task, si)
            print "Successfully created DV Port Group ", dv_port_name

    def add_vm_to_dvpg(self, si, vm_name, dv_switch, dv_port_name):
        devices = []
        vm_was_on = False
        print "Adding Contrail VM: %s to the DV port group" %(vm_name)
        vm = self.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOn:
                print "VM:%s is powered ON. Cannot do hot add now. Shutting it down" %(vm_name)
                vm_was_on= True
                task = vm.PowerOff()
                self.wait_for_task(task, si)
        nicspec = self.pyVmomi.vim.vm.device.VirtualDeviceSpec()
        nicspec.operation = self.pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.add
        nicspec.device = self.pyVmomi.vim.vm.device.VirtualVmxnet3()
        nicspec.device.wakeOnLanEnabled = True
        nicspec.device.deviceInfo = self.pyVmomi.vim.Description()
        pg_obj = self.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
        dvs_port_connection = self.pyVmomi.vim.dvs.PortConnection()
        dvs_port_connection.portgroupKey= pg_obj.key
        dvs_port_connection.switchUuid= pg_obj.config.distributedVirtualSwitch.uuid
        nicspec.device.backing = self.pyVmomi.vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
        nicspec.device.backing.port = dvs_port_connection
        devices.append(nicspec)
        vmconf = self.pyVmomi.vim.vm.ConfigSpec(deviceChange=devices)
        task = vm.ReconfigVM_Task(vmconf)
        self.wait_for_task(task, si)
        if vm_was_on:
            print "Turning VM: %s On" %(vm_name)
            task = vm.PowerOn()
            self.wait_for_task(task, si)
        print "Succesfully added  ContrailVM:%s to the DV port group" %(vm_name)

    def create_dvSwitch(self, si, network_folder, cluster, dvs_name):
        dvs = self.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], dvs_name)
        if dvs is not None:
            print("dvswitch already exists") 
            return dvs
        else:
            pnic_specs = []
            dvs_host_configs = []
            uplink_port_names = []
            pvlan_configs = []
            dvs_create_spec = self.pyVmomi.vim.DistributedVirtualSwitch.CreateSpec()
            dvs_config_spec = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
            for pvlan_idx in range(100,2001,2):
                #promiscuous  pvlan config
                pvlan_map_entry = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.PvlanMapEntry()
                pvlan_config_spec=self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.PvlanConfigSpec()
                pvlan_map_entry.primaryVlanId = pvlan_idx
                pvlan_map_entry.secondaryVlanId = pvlan_idx
                pvlan_map_entry.pvlanType = "promiscuous"
                pvlan_config_spec.pvlanEntry = pvlan_map_entry
                pvlan_config_spec.operation = self.pyVmomi.vim.ConfigSpecOperation.add
	        #isolated pvlan config
                pvlan_map_entry2 = self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.PvlanMapEntry()
                pvlan_config_spec2=self.pyVmomi.vim.dvs.VmwareDistributedVirtualSwitch.PvlanConfigSpec()
                pvlan_map_entry2.primaryVlanId = pvlan_idx
                pvlan_map_entry2.secondaryVlanId = pvlan_idx+1
                pvlan_map_entry2.pvlanType = "isolated"
                pvlan_config_spec2.pvlanEntry = pvlan_map_entry2
                pvlan_config_spec2.operation = self.pyVmomi.vim.ConfigSpecOperation.add

                pvlan_configs.append(pvlan_config_spec)
                pvlan_configs.append(pvlan_config_spec2)

            dvs_config_spec.pvlanConfigSpec = pvlan_configs

            dvs_config_spec.name = dvs_name
            dvs_config_spec.uplinkPortPolicy = self.pyVmomi.vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()
            hosts = cluster.host
            for x in range(len(hosts)):
                uplink_port_names.append("dvUplink%d" % x)

            for host in hosts:
                dvs_config_spec.uplinkPortPolicy.uplinkPortName = uplink_port_names
                dvs_config_spec.maxPorts = 2000
                #pnic_spec = self.pyVmomi.vim.dvs.HostMember.PnicSpec()
                #pnic_spec.pnicDevice = 'vmnic1'
                #pnic_specs.append(pnic_spec)
                dvs_host_config = self.pyVmomi.vim.dvs.HostMember.ConfigSpec()
                dvs_host_config.operation = self.pyVmomi.vim.ConfigSpecOperation.add
                dvs_host_config.host = host
                dvs_host_configs.append(dvs_host_config)
                dvs_host_config.backing = self.pyVmomi.vim.dvs.HostMember.PnicBacking()
                #dvs_host_config.backing.pnicSpec = pnic_specs
                dvs_config_spec.host = dvs_host_configs
            dvs_create_spec.configSpec = dvs_config_spec
            dvs_create_spec.productInfo = self.pyVmomi.vim.dvs.ProductSpec(version='5.5.0')
            task = network_folder.CreateDVS_Task(dvs_create_spec)
            self.wait_for_task(task,si)
            print "Successfully created DVS ", dvs_name
            return self.get_obj( [self.pyVmomi.vim.DistributedVirtualSwitch],dvs_name)
   

    def create_datacenter(self, dcname=None, folder=None):
        datacenter = self.get_obj([self.pyVmomi.vim.Datacenter], dcname)
        if datacenter is not None:
            print("datacenter already exists")
            return datacenter
        else:
            if len(dcname) > 79:
                raise ValueError("The name of the datacenter must be under 80 characters.")
            if folder is None:
                folder = self.service_instance.content.rootFolder
            if folder is not None and isinstance(folder, self.pyVmomi.vim.Folder):
                dc_moref = folder.CreateDatacenter(name=dcname)
                return dc_moref
    
    def wait_for_task(self, task, actionName='job', hideResult=False):
        while task.info.state == self.pyVmomi.vim.TaskInfo.State.running:
            time.sleep(2)
        if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
            if task.info.result is not None and not hideResult:
                out = '%s completed successfully, result: %s' % (actionName, task.info.result)
                print out
            else:
                out = '%s completed successfully.' % actionName
                print out
        else:
            out = '%s did not complete successfully: %s' % (actionName, task.info.error)
            raise ValueError("Something went wrong in wait_for_task")
            print out
        return task.info.result

    def print_vm_info(self, virtual_machine, depth=1):
        """
        Print information for a particular virtual machine or recurse into a
        folder with depth protection
        """
        maxdepth = 10
    
        # if this is a group it will have children. if it does, recurse into them
        # and then return
        if hasattr(virtual_machine, 'childEntity'):
            if depth > maxdepth:
                return
            vmList = virtual_machine.childEntity
            for c in vmList:
                self.print_vm_info(c, depth + 1)
            return
        summary = virtual_machine.summary
        print "Name       : ", summary.config.name
        print "Path       : ", summary.config.vmPathName
        print "Guest      : ", summary.config.guestFullName
        annotation = summary.config.annotation
        if annotation:
            print "Annotation : ", annotation
        print "State      : ", summary.runtime.powerState
        if summary.guest is not None:
            ip_address = summary.guest.ipAddress
            if ip_address:
                print "IP         : ", ip_address
        if summary.runtime.question is not None:
            print "Question  : ", summary.runtime.question.text
        print ""
    def get_obj(self, vimtype, name):
        """
        Get the vsphere object associated with a given text name
        """
        obj = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
        for c in container.view:
                if c.name == name:
                    obj = c
                    break
        return obj
    def connect_to_vcenter(self):
        from pyVim import connect
        self.service_instance = connect.SmartConnect(host=self.server,
                                                user=self.username,
                                                pwd=self.password,
                                                port=443)
        self.content = self.service_instance.RetrieveContent()
        atexit.register(connect.Disconnect, self.service_instance)

def main():
    
    vcenter_params={}
    vcenter_params['server']='10.84.24.111'
    vcenter_params['username']='admin'
    vcenter_params['password']='Contrail123!'
    vcenter_params['datacenter_name']='kiran_dc'
    vcenter_params['cluster_name']='kiran_cluster'
    vcenter_params['dvswitch_name']='kiran_dvswitch'
    vcenter_params['dvportgroup_num_ports']='16'
    vcenter_params['dvportgroup_name']='kiran_dvportgroup'
    
    
    try:
        Vcenter(vcenter_params);
        '''
        vc.connect_to_vcenter() 
        datacenter = vc.create_datacenter(dcname=vc.datacenter_name)
        cluster=vc.create_cluster(vc.cluster_name,datacenter)
        network_folder = datacenter.networkFolder
        vc.add_host(cluster,'10.84.24.61',"3C:A5:60:6F:7A:B7:C4:6C:48:28:3D:2F:A5:EC:A3:58:13:88:F6:DD",'root','c0ntrail123')
        dvs=vc.create_dvSwitch(vc.service_instance, network_folder, cluster, vc.dvswitch_name)
        vc.add_dvPort_group(vc.service_instance,dvs, vc.dvportgroup_name)
        '''
            
    except self.pyVmomi.vmodl.MethodFault as error:
        print "Caught vmodl fault : " + error.msg
        return -1
    
    return 0

# Start program
if __name__ == "__main__":
    main()

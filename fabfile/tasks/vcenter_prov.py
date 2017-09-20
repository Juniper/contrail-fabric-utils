"""
Python program for provisioning vcenter 
"""

import atexit
import time
import os

from fabfile.config import *
from fabric.contrib.files import exists
from fabfile.utils.fabos import is_xenial_or_above

class vcenter_base(object):
    def __init__(self, vcenter_base_params):
        self.pyVmomi =  __import__("pyVmomi")
        self.vcenter_server = vcenter_base_params['vcenter_server']
        self.vcenter_username = vcenter_base_params['vcenter_username']
        self.vcenter_password = vcenter_base_params['vcenter_password']
       
    def connect_to_vcenter(self):
        from pyVim import connect

        if is_xenial_or_above():
            ssl = __import__("ssl")
            context = ssl._create_unverified_context()
            self.service_instance = connect.SmartConnect(host=self.vcenter_server,
                                            user=self.vcenter_username,
                                            pwd=self.vcenter_password,
                                            port=443, sslContext=context)
        else:
            self.service_instance = connect.SmartConnect(host=self.vcenter_server,
                                            user=self.vcenter_username,
                                            pwd=self.vcenter_password,
                                            port=443)

        self.content = self.service_instance.RetrieveContent()
        atexit.register(connect.Disconnect, self.service_instance)

    def wait_for_task(self, task, actionName='job', hideResult=False):
         while task.info.state == (self.pyVmomi.vim.TaskInfo.State.running or self.pyVmomi.vim.TaskInfo.State.queued):
             time.sleep(2)
         if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
             if task.info.result is not None and not hideResult:
                 out = '%s completed successfully, result: %s' % (actionName, task.info.result)
                 print out
             else:
                 out = '%s completed successfully.' % actionName
                 print out
         elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
             out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
             raise ValueError(out)
         return task.info.result

    def answer_vm_question(vm):
        choices = vm.runtime.question.choice.choiceInfo
        default_option = None
        choice = ""
        if vm.runtime.question.choice.defaultIndex is not None:
            ii = vm.runtime.question.choice.defaultIndex
            default_option = choices[ii]
            choice = None
        while choice not in [o.key for o in choices]:
            print "VM power on is paused by this question:\n\n"
            print "\n".join(textwrap.wrap(vm.runtime.question.text, 60))
            for option in choices:
                print "\t %s: %s " % (option.key, option.label)
            if default_option is not None:
                print "default (%s): %s\n" % (default_option.label,
                                              default_option.key)
            choice = raw_input("\nchoice number: ").strip()
            print "..."
        return choice

    def poweroff(self, si, vm):
        task = vm.PowerOff()
        actionName = 'job'
        while task.info.state not in [self.pyVmomi.vim.TaskInfo.State.success or self.pyVmomi.vim.TaskInfo.State.error]:
            time.sleep(2)
        if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
            out = '%s completed successfully.' % actionName
            print out
        elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
            out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
            raise ValueError(out)
        return

    def poweron(self, si, vm):
        task = vm.PowerOn()
        actionName = 'job'
        answers = {}
        while task.info.state not in [self.pyVmomi.vim.TaskInfo.State.success or self.pyVmomi.vim.TaskInfo.State.error]:
            if vm.runtime.question is not None:
                question_id = vm.runtime.question.id
                if question_id not in answers.keys():
                    answers[question_id] = answer_vm_question(vm)
                    vm.AnswerVM(question_id, answers[question_id])
            time.sleep(2)
        if task.info.state == self.pyVmomi.vim.TaskInfo.State.success:
            out = '%s completed successfully.' % actionName
            print out
        elif task.info.state == self.pyVmomi.vim.TaskInfo.State.error:
            out = 'Error - %s did not complete successfully: %s' % (actionName, task.info.error)
            raise ValueError(out)
        return

    def set_dvs_mtu(self, dvs, mtu):
        dvs_config_spec = self.pyVmomi.vim.VmwareDistributedVirtualSwitch.ConfigSpec()
        dvs_config_spec.configVersion = dvs.config.configVersion
        dvs_config_spec.maxMtu = int(mtu)
        task = dvs.ReconfigureDvs_Task(dvs_config_spec)
        self.wait_for_task(task)
        print "Successfully reconfigured DVS %s with mtu %s" %(dvs.name, mtu)
        return dvs

    def get_dvs_portgroup(self, vimtype, portgroup_name, dvs_name):
        """
        Get the vsphere object associated with a given text name
        """
        obj = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, vimtype, True)
        for c in container.view:
            if c.name == portgroup_name:
                if c.config.distributedVirtualSwitch.name == dvs_name:
                    obj = c
                    break
        return obj

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

class sr_iov_fab(object):
    def __init__(self, sr_iov_params):
        self.pyVmomi =  __import__("pyVmomi")

        vcenter_base_params = {}
        vcenter_base_params['vcenter_server'] = sr_iov_params['vcenter_server']
        vcenter_base_params['vcenter_username'] = sr_iov_params['vcenter_username']
        vcenter_base_params['vcenter_password'] = sr_iov_params['vcenter_password']
        self.vcenter_base = vcenter_base(vcenter_base_params)

        self.dvs_name = sr_iov_params['dvs_name']
        self.dvportgroup_name = sr_iov_params['dvportgroup_name']
        self.dvportgroup_num_ports = sr_iov_params['dvportgroup_num_ports']

        self.cluster_name = sr_iov_params['cluster_name']
        self.datacenter_name = sr_iov_params['datacenter_name']
        self.datacenter_mtu = sr_iov_params['datacenter_mtu']

        self.esxi_info = sr_iov_params['esxi_info']
        self.host_list = sr_iov_params['host_list']

        try:
            self.vcenter_base.connect_to_vcenter()
            dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], self.dvs_name)
            self.vcenter_base.set_dvs_mtu(dvs, self.datacenter_mtu)
            self.add_dvPort_group(self.vcenter_base.service_instance, dvs, self.dvportgroup_name, 3)
            for host in self.host_list:
                if ('sr_iov_nics' in self.esxi_info[host]['contrail_vm']):
                    vm_name = "ContrailVM" + "-" + self.datacenter_name + "-" + self.esxi_info[host]['ip']
                    ret = self.add_sr_iov_nics(self.vcenter_base.service_instance, self.esxi_info, host, self.dvportgroup_name, vm_name)
                    if (ret == False):
                        print "Fatal Error. Cannot proceed further!"
                        return
        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return

    def add_sr_iov_nics(self, si, esxi_info, host, dv_port_name, vm_name):
        vm = self.vcenter_base.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        sr_iov_nic_list = esxi_info[host]['contrail_vm']['sr_iov_nics']
        mac_address = None
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOn:
            print "VM:%s is powered ON. Cannot do hot pci add now. Shutting it down" %(vm_name)
            self.vcenter_base.poweroff(si, vm);
        for sr_iov_nic in sr_iov_nic_list:
            user = esxi_info[host]['username']
            ip = esxi_info[host]['ip']
            password = esxi_info[host]['password']
            host_string = '%s@%s' %(user, ip)
            with settings(host_string = host_string, password = password,
                          warn_only = True, shell = '/bin/sh -l -c'):
                cmd = "vmware -v"
                out = run(cmd)
                if out.failed:
                    raise Exception("Unable to add sriov interface for physical nic %s on esxi host %s" %(sr_iov_nic, ip))
                esxi_version_info = str(out)
                esxi_version = esxi_version_info.split()[2][:3]
                cmd = "vmkchdev -l | grep %s" %sr_iov_nic
                out = run(cmd)
                if out.failed:
                     raise Exception("Unable to add sriov interface for physical nic %s on esxi host %s" %(sr_iov_nic, ip))
                nic_info = str(out)
                if len(nic_info) == 0:
                    raise Exception("Unable to add sriov interface for physical nic %s on esxi host %s" %(sr_iov_nic, ip))
                pci_id = nic_info.split()[0]
                if (esxi_version == '5.5'):
                    pci_id = pci_id[5:]
            devices = []
            nicspec = self.pyVmomi.vim.vm.device.VirtualDeviceSpec()
            nicspec.device = self.pyVmomi.vim.vm.device.VirtualSriovEthernetCard()
            nicspec.operation = self.pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.add
            nicspec.device.wakeOnLanEnabled = True
            nicspec.device.allowGuestOSMtuChange = True
            nicspec.device.deviceInfo = self.pyVmomi.vim.Description()
            pg_obj = self.vcenter_base.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
            dvs_port_connection = self.pyVmomi.vim.dvs.PortConnection()
            dvs_port_connection.portgroupKey = pg_obj.key
            dvs_port_connection.switchUuid = pg_obj.config.distributedVirtualSwitch.uuid
            nicspec.device.backing = self.pyVmomi.vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            nicspec.device.backing.port = dvs_port_connection
            nicspec.device.sriovBacking = self.pyVmomi.vim.vm.device.VirtualSriovEthernetCard.SriovBackingInfo()
            nicspec.device.sriovBacking.physicalFunctionBacking = self.pyVmomi.vim.vm.device.VirtualPCIPassthrough.DeviceBackingInfo()
            nicspec.device.sriovBacking.physicalFunctionBacking.id = pci_id
            if (mac_address):
                nicspec.device.addressType = "Manual"
                nicspec.device.macAddress = mac_address
            devices.append(nicspec)
            vmconf = self.pyVmomi.vim.vm.ConfigSpec(deviceChange=devices)
            task = vm.ReconfigVM_Task(vmconf)
            self.vcenter_base.wait_for_task(task, si)
            if mac_address is None:
               for device in vm.config.hardware.device:
                  if isinstance(device, self.pyVmomi.vim.vm.device.VirtualSriovEthernetCard):
                      devices = []
                      mac_address = device.macAddress
                      nicspec = self.pyVmomi.vim.vm.device.VirtualDeviceSpec()
                      nicspec.operation = self.pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.edit
                      nicspec.device = device
                      nicspec.device.addressType = "Manual"
                      nicspec.device.macAddress = mac_address
                      devices.append(nicspec)
                      vmconf = self.pyVmomi.vim.vm.ConfigSpec(deviceChange=devices)
                      task = vm.ReconfigVM_Task(vmconf)
                      self.vcenter_base.wait_for_task(task, si)
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOff:
            print "Turning VM: %s On" %(vm_name)
            self.vcenter_base.poweron(si, vm)
        return True

    def add_dvPort_group(self, si, dv_switch, dv_port_name):
        dv_pg = self.vcenter_base.get_dvs_portgroup([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name, dv_switch.name)
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
            dv_pg_spec.defaultPortConfig.securityPolicy.allowPromiscuous = self.pyVmomi.vim.BoolPolicy(value=False)
            dv_pg_spec.defaultPortConfig.securityPolicy.macChanges = self.pyVmomi.vim.BoolPolicy(value=True)
            dv_pg_spec.defaultPortConfig.securityPolicy.forgedTransmits = self.pyVmomi.vim.BoolPolicy(value=True)
            dv_pg_spec.defaultPortConfig.securityPolicy.inherited = False
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy = self.pyVmomi.vim.VmwareUplinkPortTeamingPolicy()
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder = self.pyVmomi.vim.VMwareUplinkPortOrderPolicy()
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort = None
            task = dv_switch.AddDVPortgroup_Task([dv_pg_spec])
            self.vcenter_base.wait_for_task(task, si)
            print "Successfully created DV Port Group ", dv_port_name

class pci_fab(object):
    def __init__(self, pci_params):
        self.pyVmomi =  __import__("pyVmomi")

        vcenter_base_params = {}
        vcenter_base_params['vcenter_server'] = pci_params['vcenter_server']
        vcenter_base_params['vcenter_username'] = pci_params['vcenter_username']
        vcenter_base_params['vcenter_password'] = pci_params['vcenter_password']
        self.vcenter_base = vcenter_base(vcenter_base_params)

        self.cluster_name = pci_params['cluster_name']
        self.datacenter_name = pci_params['datacenter_name']

        self.esxi_info = pci_params['esxi_info']
        self.host_list = pci_params['host_list']

        try:
            self.vcenter_base.connect_to_vcenter()
            for host in self.host_list:
                if ('pci_devices' in self.esxi_info[host]['contrail_vm']) and \
                   ('nic' in self.esxi_info[host]['contrail_vm']['pci_devices']):
                    vm_name = "ContrailVM" + "-" + self.datacenter_name + "-" + self.esxi_info[host]['ip']
                    ret = self.add_pci_nics(self.vcenter_base.service_instance, self.esxi_info, host, vm_name)
                    if (ret == False):
                        print "Fatal Error. Cannot proceed further!"
                        return
        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return

    def add_pci_nics(self, si, esxi_info, host, vm_name):
        vm = self.vcenter_base.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        pci_id_list = esxi_info[host]['contrail_vm']['pci_devices']['nic']
        pci_id_list.sort()
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOn:
            print "VM:%s is powered ON. Cannot do hot pci add now. Shutting it down" %(vm_name)
            self.vcenter_base.poweroff(si, vm);
        for pci_id in pci_id_list:
            device_config_list = []
            found = False
            for device_list in vm.config.hardware.device:
                if (isinstance(device_list,self.pyVmomi.vim.vm.device.VirtualPCIPassthrough)) == True \
                    and device_list.backing.id == pci_id:
                    print "pci_device already present! Not adding the pci device."
                    found = True
                    break
            if found == True:
                continue
            pci_passthroughs = vm.environmentBrowser.QueryConfigTarget(host=None).pciPassthrough
            for pci_entry in pci_passthroughs:
                if pci_entry.pciDevice.id == pci_id:
                    found = True
                    print "Found the pci device %s in the host" %(pci_id)
                    break
            if found == False:
                print "Did not find the pci passthrough device %s on the host" %(pci_id)
                return False
            print "Adding PCI device to Contrail VM: %s" %(vm_name)
            deviceId = hex(pci_entry.pciDevice.deviceId % 2**16).lstrip('0x')
            backing = self.pyVmomi.vim.VirtualPCIPassthroughDeviceBackingInfo(deviceId=deviceId,
                         id=pci_entry.pciDevice.id,
                         systemId=pci_entry.systemId,
                         vendorId=pci_entry.pciDevice.vendorId,
                         deviceName=pci_entry.pciDevice.deviceName)
            hba_object = self.pyVmomi.vim.VirtualPCIPassthrough(key=-100, backing=backing)
            new_device_config = self.pyVmomi.vim.VirtualDeviceConfigSpec(device=hba_object)
            new_device_config.operation = "add"
            new_device_config.device.connectable = self.pyVmomi.vim.vm.device.VirtualDevice.ConnectInfo()
            new_device_config.device.connectable.startConnected = True
            device_config_list.append(new_device_config)
            vm_spec=self.pyVmomi.vim.vm.ConfigSpec()
            vm_spec.deviceChange=device_config_list
            task=vm.ReconfigVM_Task(spec=vm_spec)
            self.vcenter_base.wait_for_task(task, si)
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOff:
            print "Turning VM: %s On" %(vm_name)
            self.vcenter_base.poweron(si, vm)
        return True

class vcenter_fab(object):
    def __init__(self, vcenter_params):
        self.pyVmomi =  __import__("pyVmomi")

        vcenter_base_params = {}
        vcenter_base_params['vcenter_server'] = vcenter_params['vcenter_server']
        vcenter_base_params['vcenter_username'] = vcenter_params['vcenter_username']
        vcenter_base_params['vcenter_password'] = vcenter_params['vcenter_password']
        self.vcenter_base = vcenter_base(vcenter_base_params)

        self.cluster_name = vcenter_params['cluster_name']
        self.datacenter_name = vcenter_params['datacenter_name']

        self.esxi_info = vcenter_params['esxi_info']
        self.host_list = vcenter_params['host_list']

        try:
            self.vcenter_base.connect_to_vcenter()
            sleep(20)
            for host in self.host_list:
                vm_name = "ContrailVM" + "-" + self.datacenter_name + "-" + self.esxi_info[host]['ip']
                self.configure_auto_restart(self.esxi_info[host]['ip'], vm_name)
        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return

    def configure_auto_restart(self, host_name, vm_name):
        host = self.vcenter_base.get_obj([self.pyVmomi.vim.HostSystem], host_name)
        if host is None:
            print "Host %s is not found" %(host_name)
            return
        vm = self.vcenter_base.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        if vm is None:
            print "ContrailVM %s is not found" %(vm_name)
            return
        host_settings = self.pyVmomi.vim.host.AutoStartManager.SystemDefaults()
        host_settings.enabled = True
        config = host.configManager.autoStartManager.config
        config.defaults = host_settings
        auto_power_info = self.pyVmomi.vim.host.AutoStartManager.AutoPowerInfo()
        auto_power_info.key = vm
        auto_power_info.startOrder = 1
        auto_power_info.startAction = "powerOn"
        auto_power_info.startDelay = -1
        auto_power_info.stopAction = "powerOff"
        auto_power_info.stopDelay = -1
        auto_power_info.waitForHeartbeat = 'no'
        config.powerInfo = [auto_power_info]
        host.configManager.autoStartManager.ReconfigureAutostart(config)
        print "auto_restart configured successfully for ContrailVM:%s" %(vm_name)

class dvs_fab(object):
    def __init__(self, dvs_params):
        self.pyVmomi =  __import__("pyVmomi")

        vcenter_base_params = {}
        vcenter_base_params['vcenter_server'] = dvs_params['vcenter_server']
        vcenter_base_params['vcenter_username'] = dvs_params['vcenter_username']
        vcenter_base_params['vcenter_password'] = dvs_params['vcenter_password']
        self.vcenter_base = vcenter_base(vcenter_base_params)

        self.name = dvs_params['name']
        self.datacenter_mtu = dvs_params['datacenter_mtu']
        self.dvportgroup_name = dvs_params['dvportgroup_name']
        self.dvportgroup_num_ports = dvs_params['dvportgroup_num_ports']
        self.dvportgroup_uplink = dvs_params['dvportgroup_uplink']

        self.cluster_name = dvs_params['cluster_name']
        self.datacenter_name = dvs_params['datacenter_name']

        self.esxi_info = dvs_params['esxi_info']
        self.host_list = dvs_params['host_list']

        try:
            self.vcenter_base.connect_to_vcenter()
            dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], self.name)
            self.vcenter_base.set_dvs_mtu(dvs, self.datacenter_mtu)
            self.add_dvPort_group(self.vcenter_base.service_instance, dvs, self.dvportgroup_name, self.dvportgroup_uplink)
            for host in self.host_list:
                vswitch = self.esxi_info[host]['fabric_vswitch']
                if vswitch == None:
                    vm_name = "ContrailVM" + "-" + self.datacenter_name + "-" + self.esxi_info[host]['ip']
                    self.add_vm_to_dvpg(self.vcenter_base.service_instance, vm_name, dvs, self.dvportgroup_name)
        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return

    def add_dvPort_group(self, si, dv_switch, dv_port_name, dv_port_uplink):
        dv_pg = self.vcenter_base.get_dvs_portgroup([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name, dv_switch.name)
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
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy = self.pyVmomi.vim.VmwareUplinkPortTeamingPolicy()
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder = self.pyVmomi.vim.VMwareUplinkPortOrderPolicy()
            dv_pg_spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort = dv_port_uplink
            task = dv_switch.AddDVPortgroup_Task([dv_pg_spec])
            self.vcenter_base.wait_for_task(task, si)
            print "Successfully created DV Port Group ", dv_port_name

    def add_vm_to_dvpg(self, si, vm_name, dv_switch, dv_port_name):
        devices = []
        print "Adding Contrail VM: %s to the DV port group" %(vm_name)
        vm = self.vcenter_base.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        for device in vm.config.hardware.device:
            if isinstance(device, self.pyVmomi.vim.vm.device.VirtualEthernetCard):
                nicspec = self.pyVmomi.vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = self.pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.edit
                nicspec.device = device
                nicspec.device.wakeOnLanEnabled = True
                pg_obj = self.vcenter_base.get_dvs_portgroup([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name, dv_switch.name)
                dvs_port_connection = self.pyVmomi.vim.dvs.PortConnection()
                dvs_port_connection.portgroupKey = pg_obj.key
                dvs_port_connection.switchUuid = pg_obj.config.distributedVirtualSwitch.uuid
                nicspec.device.backing = self.pyVmomi.vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                nicspec.device.backing.port = dvs_port_connection
                devices.append(nicspec)
                break
        vmconf = self.pyVmomi.vim.vm.ConfigSpec(deviceChange=devices)
        task = vm.ReconfigVM_Task(vmconf)
        self.vcenter_base.wait_for_task(task, si)
        print "Turning VM: %s On" %(vm_name)
        task = vm.PowerOn()
        self.vcenter_base.wait_for_task(task, si)
        print "Succesfully added  ContrailVM:%s to the DV port group" %(vm_name)

class Vcenter(object):
    def __init__(self, vcenter_params):
	self.pyVmomi =  __import__("pyVmomi")

        vcenter_base_params = {}
        vcenter_base_params['vcenter_server'] = vcenter_params['server']
        vcenter_base_params['vcenter_username'] = vcenter_params['username']
        vcenter_base_params['vcenter_password'] = vcenter_params['password']
        self.vcenter_base = vcenter_base(vcenter_base_params)

        self.datacenter_name = vcenter_params['datacenter_name']
        self.datacenter_mtu = vcenter_params['datacenter_mtu']
        self.dv_switches = vcenter_params['dv_switches']
        self.clusters = vcenter_params['clusters']
        self.hosts = vcenter_params['hosts']
        self.vms = vcenter_params['vms']

        try:
            self.vcenter_base.connect_to_vcenter()
            datacenter = self.create_datacenter(dcname=self.datacenter_name)
            for cluster in self.clusters:
                 cluster=self.create_cluster(cluster,datacenter)
            network_folder = datacenter.networkFolder
	    for host_info in self.hosts:
                 self.add_host(host_info[4],host_info[0],host_info[3],host_info[1],host_info[2])
            for dvs_info in self.dv_switches: 
                 dvswitch_name = dvs_info[0]
                 dvswitch_version = dvs_info[1]
                 dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], dvswitch_name)
                 if dvs:
                     dvs = self.reconfigure_dvSwitch(self.vcenter_base.service_instance, self.clusters, dvswitch_name)
                 else:
                     dvs=self.create_dvSwitch(self.vcenter_base.service_instance, network_folder, self.clusters, dvswitch_name, dvswitch_version)
                     self.configure_hosts_on_dvSwitch(self.vcenter_base.service_instance, network_folder, self.clusters, dvswitch_name)
                     self.vcenter_base.set_dvs_mtu(dvs, self.datacenter_mtu)
                     dvportgroup_name = dvs_info[2]
                     dvportgroup_num_ports = dvs_info[3]
                     self.add_dvPort_group(self.vcenter_base.service_instance, dvs, dvportgroup_name, dvportgroup_num_ports)
                     for vm_info_list in self.vms:
                          self.add_vm_to_dvpg(self.vcenter_base.service_instance, vm_info_list, dvs, dvportgroup_name)

        except self.pyVmomi.vmodl.MethodFault as error:
            print "Caught vmodl fault : " + error.msg
            return

    def create_cluster(self, cluster_name, datacenter):
        cluster = self.vcenter_base.get_obj([self.pyVmomi.vim.ClusterComputeResource], cluster_name)
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

    def add_host(self, cluster_name, hostname, sslthumbprint, username, password):
        host = self.vcenter_base.get_obj([self.pyVmomi.vim.HostSystem], hostname)
        if host is not None:
            print("host already exists")
            return host
        else:
            if hostname is None:
                raise ValueError("Missing value for name.")
            cluster = self.vcenter_base.get_obj([self.pyVmomi.vim.ClusterComputeResource], cluster_name)
            if cluster is None:
                error = 'Error - Cluster %s not found. Unable to add host %s' % (cluster_name, hostname)
                raise ValueError(error)

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
            self.vcenter_base.wait_for_task(task, self.vcenter_base.service_instance)
            host = self.vcenter_base.get_obj([self.pyVmomi.vim.HostSystem], hostname)
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

    def add_dvPort_group(self, si,dv_switch, dv_port_name, dv_port_num_ports):
        dv_pg = self.vcenter_base.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
        if dv_pg is not None:
            print("dv port group already exists")
            return dv_pg
        else:
            dv_pg_spec = self.pyVmomi.vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
            dv_pg_spec.name = dv_port_name
            dv_pg_spec.numPorts = int(dv_port_num_ports)
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
            task = dv_switch.AddDVPortgroup_Task([dv_pg_spec])
            self.vcenter_base.wait_for_task(task, si)
            print "Successfully created DV Port Group ", dv_port_name

    def add_vm_to_dvpg(self, si, vm_info_list, dv_switch, dv_port_name):
        devices = []
        vm_name = vm_info_list[0]
        vm = self.vcenter_base.get_obj([self.pyVmomi.vim.VirtualMachine], vm_name)
        pg_obj = self.vcenter_base.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
        for device_list in vm.config.hardware.device:
            if (isinstance(device_list,self.pyVmomi.vim.vm.device.VirtualVmxnet3)) == True and hasattr(device_list.backing,'port') and device_list.backing.port.portgroupKey == pg_obj.key:
                print "Contrail VM interface already present in dvpg!!"
                return 0
        print "Adding Contrail VM: %s to the DV port group" %(vm_name)
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOn:
                print "VM:%s is powered ON. Cannot do hot add now. Shutting it down" %(vm_name)
                task = vm.PowerOff()
                self.vcenter_base.wait_for_task(task, si)
        nicspec = self.pyVmomi.vim.vm.device.VirtualDeviceSpec()
        nicspec.operation = self.pyVmomi.vim.vm.device.VirtualDeviceSpec.Operation.add
        nicspec.device = self.pyVmomi.vim.vm.device.VirtualVmxnet3()
        nicspec.device.wakeOnLanEnabled = True
        nicspec.device.deviceInfo = self.pyVmomi.vim.Description()
        pg_obj = self.vcenter_base.get_obj([self.pyVmomi.vim.dvs.DistributedVirtualPortgroup], dv_port_name)
        dvs_port_connection = self.pyVmomi.vim.dvs.PortConnection()
        dvs_port_connection.portgroupKey= pg_obj.key
        dvs_port_connection.switchUuid= pg_obj.config.distributedVirtualSwitch.uuid
        nicspec.device.backing = self.pyVmomi.vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
        nicspec.device.backing.port = dvs_port_connection
        devices.append(nicspec)
        vmconf = self.pyVmomi.vim.vm.ConfigSpec(deviceChange=devices)
        task = vm.ReconfigVM_Task(vmconf)
        self.vcenter_base.wait_for_task(task, si)
        if vm.runtime.powerState == self.pyVmomi.vim.VirtualMachinePowerState.poweredOff:
            print "Turning VM: %s On" %(vm_name)
            task = vm.PowerOn()
            self.vcenter_base.wait_for_task(task, si)
        print "Succesfully added  ContrailVM:%s to the DV port group" %(vm_name)

    def create_dvSwitch(self, si, network_folder, clusters, dvs_name, dvs_version):
        dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], dvs_name)
        if dvs is not None:
            print("dvswitch already exists")
            return dvs
        else:
            pnic_specs = []
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
            if dvs_version is not None:
                dvs_create_spec.productInfo = self.pyVmomi.vim.dvs.ProductSpec(version=dvs_version)
            dvs_create_spec.configSpec = dvs_config_spec
            task = network_folder.CreateDVS_Task(dvs_create_spec)
            self.vcenter_base.wait_for_task(task,si)
            print "Successfully created DVS ", dvs_name
            return self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch],dvs_name)

    def configure_hosts_on_dvSwitch(self, si, network_folder, clusters, dvs_name):
        dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], dvs_name)
        if dvs is None:
            print "dvSwitch %s does not exist" % dvs_name
            return
        else:
            host_list = []
            for cluster_name in clusters:
                cluster = self.vcenter_base.get_obj([self.pyVmomi.vim.ClusterComputeResource], cluster_name)
                host_list.append(cluster.host)
            hosts = []
            for mo in host_list:
                for host in mo:
                    hosts.append(host)
            for each_host in dvs.config.host:
                if each_host.config.host in hosts:
                    print "%s host already exists in the dvswitch" % each_host.config.host
                    hosts.remove(each_host.config.host)
            if not hosts:
                print "No hosts left to add to dvswitch ", dvs_name
                return

            for host in hosts:
                dvs_host_configs = []
                uplink_port_names = "dvUplink1"
                dvs_config_spec = self.pyVmomi.vim.DistributedVirtualSwitch.ConfigSpec()
                dvs_config_spec.configVersion = dvs.config.configVersion
                dvs_config_spec.uplinkPortPolicy = self.pyVmomi.vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()
                dvs_config_spec.uplinkPortPolicy.uplinkPortName = uplink_port_names
                dvs_config_spec.maxPorts = 60000
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
                task = dvs.ReconfigureDvs_Task(dvs_config_spec)
                self.vcenter_base.wait_for_task(task,si)
            print "Successfully configured hosts on dvswitch ", dvs_name

    def reconfigure_dvSwitch(self, si, clusters, dvs_name):
        dvs = self.vcenter_base.get_obj([self.pyVmomi.vim.DistributedVirtualSwitch], dvs_name)
        if dvs is None:
            print "dvSwitch %s does not exist" % dvs_name
            return
        else:
            add_hosts = []
            for host_info in self.hosts:
                host = self.vcenter_base.get_obj([self.pyVmomi.vim.HostSystem], host_info[0])
                add_hosts.append(host)

            for each_host in dvs.config.host:
                if each_host.config.host in add_hosts:
                    print "%s host already exists in the dvswitch" % each_host.config.host
                    add_hosts.remove(each_host.config.host)
            if not add_hosts:
                print "No hosts left to add to dvswitch ", dvs_name
                return dvs

            print "Updating dvs_config_spec"
            for host in add_hosts:
                dvs_host_configs = []
                uplink_port_names = "dvUplink1"
                dvs_config_spec = self.pyVmomi.vim.DistributedVirtualSwitch.ConfigSpec()
                dvs_config_spec.configVersion = dvs.config.configVersion
                dvs_config_spec.uplinkPortPolicy = self.pyVmomi.vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()
                dvs_config_spec.uplinkPortPolicy.uplinkPortName = uplink_port_names
                dvs_host_config = self.pyVmomi.vim.dvs.HostMember.ConfigSpec()
                dvs_host_config.operation = self.pyVmomi.vim.ConfigSpecOperation.add
                dvs_host_config.host = host
                dvs_config_spec.host.append(dvs_host_config)
                task = dvs.ReconfigureDvs_Task(dvs_config_spec)
                self.vcenter_base.wait_for_task(task,si)
            print "Successfully reconfigured DVS ", dvs_name
            return dvs

    def create_datacenter(self, dcname=None, folder=None):
        datacenter = self.vcenter_base.get_obj([self.pyVmomi.vim.Datacenter], dcname)
        if datacenter is not None:
            print("datacenter already exists")
            return datacenter
        else:
            if len(dcname) > 79:
                raise ValueError("The name of the datacenter must be under 80 characters.")
            if folder is None:
                folder = self.vcenter_base.service_instance.content.rootFolder
            if folder is not None and isinstance(folder, self.pyVmomi.vim.Folder):
                dc_moref = folder.CreateDatacenter(name=dcname)
                return dc_moref

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

def _wait_for_task (task):
    from pyVmomi import vim
    while (task.info.state == vim.TaskInfo.State.running or
           task.info.state == vim.TaskInfo.State.queued):
        time.sleep(2)
    return task.info.state == vim.TaskInfo.State.success

def cleanup_vcenter(vcenter_info, datacenter):
    from pyVim import connect
    from pyVmomi import vim
    port = vcenter_info.get('port', 443)
    try:
        ssl = __import__("ssl")
        context = ssl._create_unverified_context()
        service_instance = connect.SmartConnect(host=vcenter_info['server'],
                            user=vcenter_info['username'],
                            pwd=vcenter_info['password'],
                            port=port, sslContext=context)
    except Exception as e:
        service_instance = connect.SmartConnect(host=vcenter_info['server'],
                            user=vcenter_info['username'],
                            pwd=vcenter_info['password'],
                            port=port) 
    content = service_instance.RetrieveContent()
    atexit.register(connect.Disconnect, service_instance)

    items = content.viewManager.CreateContainerView(content.rootFolder, [vim.Datacenter], True).view
    for obj in items:
        if obj.name == datacenter:
            dc = obj
            break
    else:
        print 'Datacenter %s does not exist' % datacenter
        return

    clusters = content.viewManager.CreateContainerView(dc,
                                       [vim.ClusterComputeResource],
                                       True).view
    hosts = []
    for cluster in clusters:
        items = content.viewManager.CreateContainerView(cluster,
                                       [vim.HostSystem], True).view
        hosts += items
    vms = []
    for host in hosts:
        vms += host.vm

    # clear the VMs
    for vm in vms:
        if vm.runtime.powerState != 'poweredOff':
            if not _wait_for_task(vm.PowerOff()):
                print 'Error while powering off vm %s' % vm.name
        if not _wait_for_task(vm.Destroy()):
            print 'Error while deleting vm %s' % vm.name

    # DV Switch & PortGroup
    items = content.viewManager.CreateContainerView(dc,
                                       [vim.dvs.DistributedVirtualPortgroup],
                                       True).view
    for obj in items:
        if not _wait_for_task(obj.Destroy()):
            print 'Error while deleting portgroup %s' % obj.name
    items = content.viewManager.CreateContainerView(dc,
                                       [vim.dvs.VmwareDistributedVirtualSwitch],
                                       True).view
    for obj in items:
        if not _wait_for_task(obj.Destroy()):
            print 'Error while deleting switch %s' % obj.name

    # clear the hosts & cluster
    for host in hosts:
        if not _wait_for_task(host.EnterMaintenanceMode(30)):
            print 'Error in host.EnterMaintenanceMode for %s' % host.name
        if not _wait_for_task(host.Destroy()):
            print 'Error while deleting host %s' % host.name
    for cluster in clusters:
        if not _wait_for_task(cluster.Destroy()):
            print 'Error while deleting cluster %s' % cluster.name

    # delete datacenter
    if not _wait_for_task(dc.Destroy()):
        print 'Error while deleting datacenter %s' % dc.name


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

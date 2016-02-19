import string

template = string.Template(
'''.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "$__hw_version__"
vmci0.present = "TRUE"
hpet0.present = "TRUE"
nvram = "$__vm_name__.nvram"
virtualHW.productCompatibility = "hosted"
powerType.powerOff = "soft"
powerType.powerOn = "hard"
powerType.suspend = "hard"
powerType.reset = "soft"
displayName = "$__vm_name__"
extendedConfigFile = "$__vm_name__.vmxf"
floppy0.present = "FALSE"
numvcpus = "2"
cpuid.coresPerSocket = "1"
scsi0.present = "TRUE"
scsi0.sharedBus = "none"
scsi0.virtualDev = "lsilogic"
memsize = "8228"
sched.mem.min = "8228"
scsi0:0.present = "TRUE"
scsi0:0.fileName = "$__vm_name__.vmdk"
scsi0:0.deviceType = "scsi-hardDisk"
ethernet0.present = "TRUE"
ethernet0.virtualDev = "$__eth0_type__"
ethernet0.networkName = "$__fab_pg__"
ethernet0.addressType = "static"
ethernet0.address = "$__vm_mac__"
chipset.onlineStandby = "FALSE"
guestOS = "ubuntu-64"
keyboard.typematicMinDelay = "2000000"
tools.upgrade.policy = "upgradeatpowercycle"
$__extension_params__
''')

esxi_eth1_template = string.Template(
'''ethernet1.present = "TRUE"
ethernet1.virtualDev = "e1000"
ethernet1.networkName = "$__vm_pg__"
ethernet1.addressType = "generated"
''')

esxi_eth2_template = string.Template(
'''ethernet2.present = "TRUE"
ethernet2.virtualDev = "e1000"
ethernet2.networkName = "$__data_pg__"
ethernet2.addressType = "generated"
''')

vcenter_ext_template = '''pciBridge0.present = "TRUE"
svga.present = "TRUE"
pciBridge4.present = "TRUE"
pciBridge4.virtualDev = "pcieRootPort"
pciBridge4.functions = "8"
pciBridge5.present = "TRUE"
pciBridge5.virtualDev = "pcieRootPort"
pciBridge5.functions = "8"
pciBridge6.present = "TRUE"
pciBridge6.virtualDev = "pcieRootPort"
pciBridge6.functions = "8"
pciBridge7.present = "TRUE"
pciBridge7.virtualDev = "pcieRootPort"
pciBridge7.functions = "8"
'''

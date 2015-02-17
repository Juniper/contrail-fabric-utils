import string

template = string.Template(
'''.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "8"
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
numvcpus = "4"
cpuid.coresPerSocket = "4"
scsi0.present = "TRUE"
scsi0.sharedBus = "none"
scsi0.virtualDev = "lsilogic"
memsize = "8228"
scsi0:0.present = "TRUE"
scsi0:0.fileName = "$__vm_name__.vmdk"
scsi0:0.deviceType = "scsi-hardDisk"
ethernet0.present = "TRUE"
ethernet0.virtualDev = "e1000"
ethernet0.networkName = "$__fab_pg__"
ethernet0.addressType = "static"
ethernet0.address = "$__vm_mac__"
chipset.onlineStandby = "FALSE"
guestOS = "ubuntu-64"
$__extension_params__
''')

esxi_ext_template = string.Template(
'''ethernet1.present = "TRUE"
ethernet1.virtualDev = "e1000"
ethernet1.networkName = "$__vm_pg__"
ethernet1.addressType = "generated"
''')

vcenter_ext_template = '''pciBridge0.present = "TRUE"
svga.present = "TRUE
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


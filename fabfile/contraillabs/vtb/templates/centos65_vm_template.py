import string

template = string.Template("""
[DEFAULT]
name=$__name__
description="VM $__name__"
os_type=Linux
os_variant=rhel6
distro=centos65
hostname=$__name__
nameserver=10.84.5.100,8.8.8.8

[COMPUTE]
host_interface=$__host_interface__
bridge_interface=$__bridge_interface__

[SYSTEM]
vcpus=2
ram=4096
disk='path=/var/lib/libvirt/images/$__name__.img,size=4'
graphics=vnc,listen=0.0.0.0
autoconsole=no
virtualization=hvm 

[IMAGE]
location=/root/CentOS-6.5-x86_64-bin-DVD1.iso
kickstart=$__name__ks.cfg

[PRIVATE_NETWORK]
bootproto=static
ipaddress=$__ipaddress__
netmask=255.255.255.0
gateway=192.168.122.254
network='network=default,model=virtio

[PUBLIC_NETWORK]
bootproto=dhcp
network='bridge=$__bridge_interface__'
""")

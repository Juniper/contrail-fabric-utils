import string

template = string.Template("""
# Install OS instead of upgrade
install
cdrom

# use custom network file
%include /tmp/network.ks

# System language
lang en_US.UTF-8

# System keyboard
keyboard us

# Root password
rootpw c0ntrail123

# System authorization information
auth  --useshadow  --enablemd5

# System bootloader configuration
bootloader --location=mbr

# Partition clearing information
clearpart --linux --all

# Use text mode install
text

# Firewall configuration
firewall --enabled

# Run the Setup Agent on first boot
firstboot --disable

# Reboot after installation
reboot

# SELinux configuration
selinux --disabled

# Do not configure the X Window System
skipx

# System timezone
timezone  America/Los_Angeles

# Clear the Master Boot Record
zerombr

# Allow anaconda to partition the system as needed
autopart

# enable logging
logging --level=debug

# Create contrail user Optional
user --name=contrail --groups sudo --plaintext --password c0ntrail123

%pre --log=/root/pre-ks.log
set -x
$__public_network_lines__

NET_COMMAND="network --device $__private_net_intf__ --bootproto=static --ip $__ipaddress__ --netmask $__netmask__ --gateway $__gateway__ --nameserver $__nameserver__ --hostname $__hostname__"
echo "$NET_COMMAND" >> /tmp/network.ks
%end

%packages --nobase
@core
%end

%post --log=/root/post-ks.log
set -x
# Disable IP tables
service iptables stop
/sbin/chkconfig iptables off

# Disable requiretty
sed -i s/'Defaults    requiretty'/'#Defaults    requiretty'/g /etc/sudoers

# Enable no password sudo access to contrail
echo "contrail   ALL=(ALL)       NOPASSWD: ALL" >> /etc/sudoers.d/contrail
chmod 0440 /etc/sudoers.d/contrail

# Update /etc/hosts if not populated correctly
grep $(hostname) /etc/hosts > /dev/null
if [ $? != 0 ]; then
    ip=$(hostname -I)
    echo "$ip $(hostname) $(hostname | grep -o "^[^\.]*")" >> /etc/hosts
fi

echo UseDNS no >> /etc/ssh/sshd_config
# End final steps
%end
""")

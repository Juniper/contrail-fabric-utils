# Copyright (c) 2016 Netronome Systems, Inc. All rights reserved.

import os
import copy
import glob

from fabric.api import env, settings, sudo, local, run
from fabric.utils import abort
from fabric.contrib.files import exists

from fabfile.config import *
from fabfile.utils.fabos import get_as_sudo
import tempfile

from iface_parser import IfaceParser

class ProvisionNsAgilioVrouter():

    def __init__(self, host_string, ns_agilio_vrouter, bond, control_data):
        self._accelerated = None
        self._bonded = False
        self._node_compute = {}
        self._node_bond = {}
        self._node_control_data = {}
        self._host_string = host_string

        # copy env.ns_agilio_vrouter from testbed
        self._ns_agilio_vrouter_dict = copy.deepcopy(ns_agilio_vrouter)
        # copy control_data
        self._control_data = copy.deepcopy(control_data)
        # copy bond from testbed
        self._bond_dict = copy.deepcopy(bond)

        # Verify node is to be accelerated
        if self._ns_agilio_vrouter_dict is not None:
            if self._host_string in self._ns_agilio_vrouter_dict:
                # obtain value of host_string key from dict
                self._node_compute = self._ns_agilio_vrouter_dict[self._host_string]
                self._accelerated = True
            else:
                self._accelerated = False
        else:
            self._accelerated = False
            # TBD - force fail as below?
            raise ValueError('_ns_agilio_vrouter_dict cannot be None')

        # Verify control_data is defined and node is in control_data
        if self._control_data is not None:
            if self._host_string in self._control_data:
                # obtain value of host_string key from dict
                self._node_control_data = self._control_data[self._host_string]
            else:
                raise ValueError('%s not in control_data' % self._host_string)
        else:
            raise ValueError('control_data must be defined in the testbed')

        # check if node is bonded
        if self._bond_dict is not None:
            if self._host_string in self._bond_dict:
                # obtain value of host_string key from dict
                self._node_bond = self._bond_dict[self._host_string]
                # check members to determine if nfp is part of bond
                for member in self._node_bond['member']:
                    if member.startswith('nfp_p'):
                        self._bonded = True


    def setup(self):
        # device should specify nfp_pX or bondX device name
        netdev_name = self._node_control_data['device']

        if self._accelerated:
            self.check_boot()
            self.check_kernel()
            self.check_netdevs()
            self.check_cpld()
            self.update_agent_conf(netdev_name)
            self.update_agent_param(netdev_name)
            self.update_interfaces_file(netdev_name)
            self.install_openstack_integration()
            self.configure_virtiorelayd()
            if not self.add_hugepage_grub():
                raise ValueError('Failed to add hugepage config to grub')
            self.enable_virtiorelayd()
        else:
            # teardown acceleration only if nfp device
            #   if new netdev name is nfp_pX (corenic)
            #   if we are bonded (only returns true nfp_pX in bond members)
            if netdev_name.startswith('nfp_p') or self._bonded:
                self.check_netdevs()
                self.update_agent_conf(netdev_name)
                self.update_agent_param(netdev_name)
                self.update_interfaces_file(netdev_name)
                self.remove_hugepage_grub()
                self.disable_virtiorelayd()


    def teardown(self):
        # device should specify nfp_pX or bondX device name
        netdev_name = self._node_control_data['device']
        self._accelerated = False
        if netdev_name.startswith('nfp_p') or self._bonded:
            self.update_interfaces_file(netdev_name)
            self.remove_hugepage_grub()
            self.disable_virtiorelayd()


    def check_boot(self):
        print "Check boot"
        sudo("cd /opt/netronome/srcpkg/; tar -xvf ns-dpdk-srcpkg.tgz > /dev/null")
        sudo("cd /opt/netronome/srcpkg/ns-dpdk-srcpkg/virtio_relay/; python -m netronome.iommu_check")

        # msr tools
        sudo("modprobe msr")
        out = sudo("rdmsr -cx 0x3a -f 2:2")
        if out.strip() != "0x1":
            abort("VT-d is not enabled on this system.")


    def check_netdevs(self):
        """Checks if nfp_p* device in /etc/network/interfaces file
           Command is executed on fabric node
        """

        out = None
        with settings(warn_only=True):
            out = sudo("ifquery --list | grep -cq nfp_p*")

        if out.return_code != 0:
            abort("No nfp_p* interface found on the system.")


    def check_kernel(self):
        """Checks if currently loaded kernel has err47 patches
           Command is executed on fabric node
        """

        sudo("/opt/netronome/bin/ns-vrouter-ctl check kernel")


    def check_cpld(self):
        """Check if cpld and cfg rom meet minimums"""

        sudo("/opt/netronome/bin/ns-vrouter-ctl check cpld")


    def update_agent_conf(self, name):
        """Updates /etc/contrail/contrail-vrouter-agent.conf
           Commands are executed on fabric node
        """

        out = sudo("openstack-config --set /etc/contrail/contrail-vrouter-agent.conf VIRTUAL-HOST-INTERFACE physical_interface %s" % name)
        out = sudo("/opt/netronome/bin/ns-vrouter-ctl check mac %s" % name)
        out = sudo("openstack-config --set /etc/contrail/contrail-vrouter-agent.conf DEFAULT physical_interface_mac %s" % out)


    def update_agent_param(self, name):
        """Updates /etc/contrail/agent_param
           Commands are executed on fabric node
        """

        sudo("sed 's/dev=.*/dev=%s/g' /etc/contrail/agent_param > /tmp/agent_param.netro" % name)
        sudo("mv /tmp/agent_param.netro /etc/contrail/agent_param")


    def install_openstack_integration(self):
        """Executes /opt/netronome/openstack/install.sh on fabric node
        """

        sudo("NS_VROUTER_OPENSTACK_SUPPRESS_CLOUD_ARCHIVE=1 \
                 /opt/netronome/openstack/install.sh")


    def configure_virtiorelayd(self):
        print "AGILIO DICT"
        print self._ns_agilio_vrouter_dict
        print "BOND DICT"
        print self._node_bond
        print "CONTROL_DATA DICT"
        print self._node_control_data

        # TODO validate dictionary data
        for k,v in self._ns_agilio_vrouter_dict[self._host_string].iteritems():
            if k == 'coremask':
                print "VIRTIORELAYD_CPU_MASK: (%s, %s)" % (k,v)
                sudo("sed 's/VIRTIORELAYD_CPU_MASK=.*/VIRTIORELAYD_CPU_MASK=%s/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro" % v)
                sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")
            elif k == 'pinning_mode':
                print "Setting VIRTIORELAYD_CPU_PINS: (%s, %s)" % (k,v)
                sudo("sed 's/VIRTIORELAYD_CPU_PINS=.*/VIRTIORELAYD_CPU_PINS=%s/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro" % v)
                sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")
            elif k == 'huge_page_alloc':
                print "Setting VIRTIORELAYD_HUGEPAGE_MEMORY_SIZE: (%s, %s)" % (k,v)
                sudo("sed 's/VIRTIORELAYD_HUGEPAGE_MEMORY_SIZE=.*/VIRTIORELAYD_HUGEPAGE_MEMORY_SIZE=%s/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro" % v)
                sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")
            elif k == 'log_level':
                print "Setting VIRTIORELAYD_LOG_LEVEL: (%s, %s)" % (k,v)
                sudo("sed 's/VIRTIORELAYD_LOG_LEVEL=.*/VIRTIORELAYD_LOG_LEVEL=%s/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro" % v)
                sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")

            else:
                print "Key: %s Value: %s is not recognized.. skipping" % (k,v)


    def remove_hugepage_grub(self, update_grub=True):
        # the following sed commands will not touch comment lines
        print "Removing hugepage config from GRUB_CMDLINE_LINUX"
        sudo("sed -e 's/\(^GRUB_CMDLINE_LINUX=.*\)\(default_hugepagesz=\w*\s*\)\(.*\)/\\1\\3/g' -e 's/\(^GRUB_CMDLINE_LINUX=.*\)\(hugepagesz=\w*\s*\)\(.*\)/\\1\\3/g' -e 's/\(^GRUB_CMDLINE_LINUX=.*\)\(hugepages=\w*\s*\)\(.*\)/\\1\\3/g' /etc/default/grub > /tmp/grub.netro")
        sudo("mv /tmp/grub.netro /etc/default/grub")

        print "Removing hugepage config from GRUB_CMDLINE_LINUX_DEFAULT"
        sudo("sed -e 's/\(^GRUB_CMDLINE_LINUX_DEFAULT=.*\)\(default_hugepagesz=\w*\s*\)\(.*\)/\\1\\3/g' -e 's/\(^GRUB_CMDLINE_LINUX_DEFAULT=.*\)\(hugepagesz=\w*\s*\)\(.*\)/\\1\\3/g' -e 's/\(^GRUB_CMDLINE_LINUX_DEFAULT=.*\)\(hugepages=\w*\s*\)\(.*\)/\\1\\3/g' /etc/default/grub > /tmp/grub.netro")
        sudo("mv /tmp/grub.netro /etc/default/grub")

        # remove trailing whitespace (will touch comment lines)
        sudo("sed -e 's/\s*\"$/\"/g' /etc/default/grub > /tmp/grub.netro")
        sudo("mv /tmp/grub.netro /etc/default/grub")

        if update_grub:
            sudo("update-grub")

    def add_hugepage_grub(self, update_grub=True):
        self.remove_hugepage_grub(update_grub=False)
        print "Adding hugepage config to GRUB_CMDLINE_LINUX_DEFAULT"

        if self._ns_agilio_vrouter_dict[self._host_string]:
            hugepage_sz = self._ns_agilio_vrouter_dict[self._host_string]['huge_page_size']
            if hugepage_sz != "1G" and hugepage_sz != "2M":
                print "Invalid hugepage size"
                return False

            hugepage_total = self._ns_agilio_vrouter_dict[self._host_string]['huge_page_alloc']
            hugepage_total_sz = 0
            hugepage_ct = 0
            if not hugepage_total.endswith("G"):
                print "Invalid allocation"
                return False
            else:
                hugepage_total = hugepage_total[:-1]  # Strip the 'G'
                hugepage_total_sz = int(hugepage_total)

            if hugepage_sz == "1G":
                hugepage_ct = hugepage_total_sz
            elif hugepage_sz == "2M":
                hugepage_ct = hugepage_total_sz * 512  # 512 2M pages in 1G

        grub_cmdline_add = "default_hugepagesz=%s hugepagesz=%s hugepages=%s" % (hugepage_sz, hugepage_sz, hugepage_ct)
        print grub_cmdline_add
        sudo("sed -e 's/\(^GRUB_CMDLINE_LINUX_DEFAULT=.*\)\"$/\\1 %s\"/' /etc/default/grub > /tmp/grub.netro" % grub_cmdline_add)
        sudo("mv /tmp/grub.netro /etc/default/grub")

        if update_grub:
            sudo("update-grub")

        return True


    def disable_virtiorelayd(self):
        print "Disable virtiorelayd"
        # we dont need to stop virtiorelayd because the node will reboot
        # modify conf file
        sudo("sed 's/VIRTIORELAYD_ENABLE=.*/VIRTIORELAYD_ENABLE=false/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro")
        sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")

    def enable_virtiorelayd(self):
        print "Enable virtiorelayd"
        # modify conf file
        sudo("sed 's/VIRTIORELAYD_ENABLE=.*/VIRTIORELAYD_ENABLE=true/g' /etc/default/virtiorelayd > /tmp/virtiorelayd.netro")
        sudo("mv /tmp/virtiorelayd.netro /etc/default/virtiorelayd")


    def update_interfaces_file(self, name):
        """Parses and modifies /etc/network/interfaces
           /etc/network/interfaces is downloaded from fabric node and
           saved as temp file on fabric local node.  The temp file is
           parsed and modified for ns-agilio-vrouter integration.
           The temp file is then uploaded to the fabric node.

        """

        # create tempfile
        (iface_tmp_d, iface_tmp_path) = tempfile.mkstemp()
        # download tempfile
        get_as_sudo("/etc/network/interfaces", iface_tmp_path)

        # parse and modify tempfile
        if self._accelerated:
            self._accelerate(iface_tmp_path, name)
        else:
            self._decelerate(iface_tmp_path, name)

        # upload tempfile
        put(local_path=iface_tmp_path, remote_path="/etc/network/interfaces", use_sudo=True)
        sudo("cat /etc/network/interfaces")
        # delete tempfile local
        os.close(iface_tmp_d)
        os.remove(iface_tmp_path)


    def _remove_redundant_lines(self, iparser):
        ifaces = iparser.get_iface_order()
        redundant_lines = []
        redundant_lines.append("post-down ifconfig %s down")
        redundant_lines.append("pre-up ifconfig %s up")
        for iface in ifaces:
            iface_lines = iparser.get_iface_lines(iface)
            rm_lines = []
            for r in redundant_lines:
                to_rm = r % iface
                for l in iface_lines:
                    tmp_line = l.strip()
                    if to_rm in tmp_line:
                        print "Removing line %s" % to_rm
                        rm_lines.append(l)

            for l in rm_lines:
                iface_lines.remove(l)

            iparser.replace_iface_lines(iface, iface_lines)


    def _reorder_interfaces(self, iparser, name):
        print "Reordering interfaces"
        # get currently ordered interfaces
        ifaces = iparser.get_iface_order()

        end_list = []
        # add bond to top of list
        if self._bonded:
            end_list.append(name)

        # add nfp_pX devices (if in ordered list)
        for i in range(8):
            nfp_name = "nfp_p%s" % i
            if nfp_name in ifaces:
                end_list.append(nfp_name)

        # add vhost
        end_list.append("vhost0")

        tmp_ifaces_lines = {}
        # backup and remove old interfaces
        for dev in end_list:
            tmp_ifaces_lines[dev] = iparser.get_iface_lines(dev)
            # add new line.  will be cleaned after reorder
            tmp_ifaces_lines[dev].append("\n")
            iparser.remove_iface(dev)

        # restore interfaces in order
        prev_iface = iparser.get_iface_order()[-1]
        prev_iface_lines = iparser.get_iface_lines(prev_iface)
        prev_iface_lines.append("\n")
        iparser.replace_iface_lines(prev_iface, prev_iface_lines)
        for dev in end_list:
            iparser.insert_iface_after(tmp_ifaces_lines[dev], prev_iface)
            prev_iface = dev

        iparser.clean_extra_lines()


    def _fix_bond_slaves(self, iparser, name):
        bond_netdev = iparser.get_iface_lines(name)
        hit_idx = None
        for l in bond_netdev:
            if "bond-slaves none" in l:
                print "Found bond-slaves none"
                hit_idx = bond_netdev.index(l)
                break

        if not hit_idx:
            print "bond-slaves none not found. skipping"
        else:
            # make line
            replace_str = "    bond-slaves"
            for member in self._node_bond['member']:
                replace_str += (" %s" % member)
            replace_str += "\n"

            print "replacing line %s with %s" % (bond_netdev[hit_idx], replace_str)
            bond_netdev[hit_idx] = replace_str
            iparser.replace_iface_lines(name, bond_netdev)


    def _accelerate(self, iface_file_path, name):
        iface = []
        parser = IfaceParser(iface_file_path)
        if not parser.has_iface(name):
            return 1

        if not parser.has_iface("nfp_p0"):
            return 1

        # remove existing nfp_fallback netdev
        if parser.has_iface("nfp_fallback"):
            parser.remove_iface("nfp_fallback")

        # add pre-up / pre-down from primary interface
        iface = parser.get_iface_lines(name)
        # add ifdown
        iface = parser.iface_add_value(iface, \
            "pre-down /opt/netronome/bin/ns-vrouter-ctl stop\n")
        iface = parser.iface_add_value(iface, \
            "pre-up /opt/netronome/bin/ns-vrouter-ctl start\n")
        # rewrite interface
        parser.replace_iface_lines(name, iface)

        netdevs = []
        netdevs.append("vhost0")

        for n in netdevs:
            # append netdev value
            iface = parser.get_iface_lines(n)
            iface = parser.iface_add_value(iface, \
                "pre-up ip link show dev nfp_fallback up 2>/dev/null | grep -q .\n")
            parser.replace_iface_lines(n, iface)

        if self._bonded:
            self._fix_bond_slaves(parser, name)

        # TODO check vhost0 mac
        parser.clean_extra_lines()
        self._reorder_interfaces(parser, name)
        self._remove_redundant_lines(parser)
        parser.write_ifaces()


    def _decelerate(self, iface_file_path, name):
        iface = []
        parser = IfaceParser(iface_file_path)
        if not parser.has_iface(name):
            return 1

        # remove existing nfp_fallback netdev
        if parser.has_iface("nfp_fallback"):
            parser.remove_iface("nfp_fallback")

        # del pre-up / pre-down from primary interface
        iface = parser.get_iface_lines(name)
        iface = parser.iface_del_value(iface, \
            "pre-down /opt/netronome/bin/ns-vrouter-ctl stop\n")
        iface = parser.iface_del_value(iface, \
            "pre-up /opt/netronome/bin/ns-vrouter-ctl start\n")
        # rewrite interface
        parser.replace_iface_lines(name, iface)

        netdevs = []
        netdevs.append("vhost0")

        for n in netdevs:
            # remove netdev value
            iface = parser.get_iface_lines(n)
            iface = parser.iface_del_value(iface, \
                "pre-up ip link show dev nfp_fallback up 2>/dev/null | grep -q .\n")
            parser.replace_iface_lines(n, iface)

        if self._bonded:
            self._fix_bond_slaves(parser, name)

        # TODO check vhost0 mac
        parser.clean_extra_lines()
        self._reorder_interfaces(parser, name)
        self._remove_redundant_lines(parser)
        parser.write_ifaces()



#!/usr/bin/env python
import sys
import importlib
import ConfigParser
from time import sleep

from paramiko import ChannelException
from fabric.exceptions import NetworkError

from fabfile.config import *
from fabfile.utils.host import hstr_to_ip, get_env_passwords

__all__ = ['create_vm', 'setup_vtb']

VIRT_PKG_LIST = ['qemu-kvm', 'libvirt-bin', 'virtinst']
DEBIAN_DISTRO = ['ubuntu1204', 'ubuntu1404']
RHEL_DISTRO = ['centos65']

class VirtualMachine(object):
    def __init__(self, vm_template):
        self.vm_template = vm_template
        self.distro = self.vm_template.get('DEFAULT', 'distro')
        self.vm_hostname = self.vm_template.get('DEFAULT', 'hostname')
        self.vm_ip = self.vm_template.get('PRIVATE_NETWORK', 'ipaddress')
        self.virt_pkgs = VIRT_PKG_LIST
        self.vmi = {}

    def execute(self, cmd):
        sudo(cmd)

    def exec_status(self, cmd):
        with settings(hide('everything'), warn_only=True):
            if sudo(cmd).failed:
                return False
        return True

    def exec_out(self, cmd, gateway=None, host=None, password=None,
                 hideit=None, warn_only=False):
        settings_kwargs = {'warn_only' : warn_only}   
        if gateway: settings_kwargs.update({'gateway' : gateway})
        if host: settings_kwargs.update({'host_string' : host})
        if password: settings_kwargs.update({'password' : password})

        if hideit:
            with settings(hide('%s' % hideit), **settings_kwargs): 
                return sudo(cmd).strip()
        else:
            with settings(**settings_kwargs): 
                return sudo(cmd).strip()

    def install_virt_pkgs(self):
        pkgs = ' '.join(self.virt_pkgs)
        while ('Could not get lock' in
               self.exec_out('apt-get install -y %s' % pkgs,
                             hideit='stderr', warn_only=True)):

            print "Waiting for dpkg lock..."
            sleep(3)

    def create_bridge_interface(self):
        host_intf = self.vm_template.get('COMPUTE', 'host_interface')
        bridge_intf = self.vm_template.get('COMPUTE', 'bridge_interface')

        # Check if compute host interface exixts
        is_host_intf_exists = 'ifconfig %s' % host_intf
        if not self.exec_status(is_host_intf_exists):
            raise RuntimeError("Interface [%s] dosen't exists" % host_intf)

        # Check if IP address configured in compute host interface
        is_host_intf_configured = ['ifconfig %s |' % host_intf, 
                                   'grep "inet addr:"']
        if not self.exec_status(' '.join(is_host_intf_configured)):
            # Check if bridge interface already configured
            is_br_intf_configured = ["ifconfig %s |" % bridge_intf,
                                     "grep 'inet addr:' |",
                                     "cut -d: -f2 |",
                                     "awk '{ print $1}'"]
            if self.exec_status(' '.join(is_br_intf_configured)):
                print "Bridge Interface %s already created." % bridge_intf
                return
        else:
            # Check if br interface name is already used
            if self.exec_status('ifconfig %s' % bridge_intf):
                raise RuntimeError("[%s] already used,"
                                   " please use another name" % bridge_intf)

        # Create bridge interface
        self.execute('virsh iface-bridge %s %s' % (host_intf, bridge_intf))

    def frame_virt_commandline(self):
        cmd = ['virt-install']
        if self.vm_template.has_section('PUBLIC_NETWORK'):
            cmd.append('--network bridge=br0')

        ks_file = self.vm_template.get('IMAGE', 'kickstart')
        cmd += ['--name %s' % self.vm_hostname,
               '--description "Virtual Machine %s"' % self.vm_hostname,
               '--os-type=%s' % self.vm_template.get('DEFAULT', 'os_type'),
               '--os-variant=%s' % self.vm_template.get('DEFAULT',
                                                        'os_variant'),
               '--vcpus=%s' % self.vm_template.get('SYSTEM', 'vcpus'),
               '--ram=%s' % self.vm_template.get('SYSTEM', 'ram'),
               '--disk %s' % self.vm_template.get('SYSTEM', 'disk'),
               '--location %s' % self.vm_template.get('IMAGE', 'location'),
               '--network network=default,model=virtio',
               '--graphics vnc,listen=0.0.0.0',
               '--%s' % self.vm_template.get('SYSTEM', 'virtualization'),
               '--extra-args "ks=file:/%s"' % self.ks_file,
               '--initrd-inject=/root/%s' % self.ks_file,
              ]
        if self.vm_template.get('SYSTEM', 'autoconsole') == 'no':
            cmd.append('--noautoconsole')

        return ' '.join(cmd)

    def create(self):
        # To be implemented in the derived class
        pass

    def verify_connectivity(self, state='up'):
        sys.stdout.write('.')
        cmd = 'ping -c 1 %s | grep "1 received"' % self.vm_ip
        if state == 'down':
            cmd = 'ping -c 1 %s | grep "0 received"' % self.vm_ip
        while not self.exec_status(cmd):
            sys.stdout.write('.')
            sys.stdout.flush()
            sleep(2)
            continue

    def wait_until_vm_is_up(self):
        print 'Waiting for VM (%s) to start booting...' % self.vm_ip
        self.verify_connectivity()
        print '\nVM (%s) started booting,'\
              'waiting till boot process is complete...' % self.vm_ip
        self.verify_connectivity(state='down')
        print '\nVM (%s) booted up sucessfully...' % self.vm_ip

    def find_public_net_ip(self):
        get_public_ip = ["ifconfig eth0 |",
                         "grep 'inet addr:' |",
                         "cut -d: -f2 |",
                         "awk '{ print $1}'"
                        ]
        return self.exec_out(' '.join(get_public_ip),
                             host='root@%s' % self.vm_ip,
                             password='c0ntrail123',
                             warn_only=True,
                             gateway=env.host_string,
                             hideit='everything')

    def start(self):
        if 'shut off' in self.exec_out('virsh domstate %s' % self.vm_hostname):
            self.execute('virsh start %s' % self.vm_hostname)
            print "Waiting for VM (%s) to start..." %  self.vm_hostname
            self.verify_connectivity()

        if self.vm_template.has_section('PUBLIC_NETWORK'):
            while True:
                try:
                    public_ip = self.find_public_net_ip()
                    break
                except ChannelException, NetworkError:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    sleep(2)
                    continue
            self.vmi.update({'eth0' : public_ip})

        self.execute('virsh domstate %s' % self.vm_hostname)
        print "VM [%s] is running." % self.vm_hostname
        print "VM [%s] interface: %s" % (self.vm_hostname, self.vmi)


class DebianVM(VirtualMachine):
    def __init__(self, vm_template):
        super(DebianVM, self).__init__(vm_template)

    def make_kickseed_file(self):
        pass

    def create(self):
        self.install_virt_pkgs()
        self.create_bridge_intf()
        self.make_kickseed_file()
        cmd = self.frame_virt_commandline()
        self.execute(cmd)
        self.wait_until_vm_is_up()
        self.start()
        return self.vmi


class RhelVM(VirtualMachine):
    def __init__(self, vm_template):
        super(RhelVM, self).__init__(vm_template)

    def make_kickstart_file(self):
        try:
            kickstart = importlib.import_module(
             'fabfile.contraillabs.vtb.templates.%s_ks_template' % self.distro)
        except ImportError:
            kickstart = importlib.import_module(
                            'templates.%s_ks_template' % self.distro)

        nameserver = self.vm_template.get('DEFAULT', 'nameserver')
        public_network_lines = ''
        private_net_intf = 'eth0'
        if self.vm_template.has_section('PUBLIC_NETWORK'):
            public_network_lines += 'NET_COMMAND="network\
                --device eth0 --onboot yes --bootproto dhcp\
                --nameserver %s --hostname %s"' % (nameserver, self.vm_hostname)
            public_network_lines += '\necho "$NET_COMMAND" > /tmp/network.ks'
            private_net_intf = 'eth1'
        # Update Vm interaface information.
        self.vmi = {private_net_intf : self.vm_ip}

        ks_config = kickstart.template.safe_substitute({
            '__public_network_lines__': public_network_lines,
            '__private_net_intf__' : private_net_intf,
            '__ipaddress__' : self.vm_ip,
            '__netmask__' : self.vm_template.get('PRIVATE_NETWORK', 'netmask'),
            '__gateway__' : self.vm_template.get('PRIVATE_NETWORK', 'gateway'),
            '__nameserver__' : nameserver,
            '__hostname__' : self.vm_hostname,
        })

        self.ks_file = '%s_ks.cfg' % self.vm_hostname
        with open(self.ks_file, 'w+') as ks_cfg_file:
            ks_cfg_file.write(ks_config)
        put(self.ks_file, use_sudo=True)

    def create(self):
        self.install_virt_pkgs()
        self.create_bridge_interface()
        self.make_kickstart_file()
        cmd = self.frame_virt_commandline()
        self.execute(cmd)
        self.wait_until_vm_is_up()
        self.start()


class VMLauncher(object):
    def __init__(self, host, vm_template):
        self.vm_template = ConfigParser.ConfigParser()
        self.vm_template.read(vm_template)
        self.distro = self.vm_template.get('DEFAULT', 'distro')

    def launch(self):
        if self.distro in ['ubuntu1204', 'ubuntu1404']:
            vm = DebianVM(self.vm_template)
        elif self.distro in ['centos65', 'redhat', 'centoslinux']:
            vm =RhelVM(self.vm_template)
        vm.create()
        return vm.vmi

@task
def create_vm(host, vm_template):
    with settings(host_string=host, password=get_env_passwords(host)):
        vm = VMLauncher(host, vm_template)
        vmi = vm.launch()
    return vmi


def get_compute_host_intf(compute):
    compute_ip = hstr_to_ip(compute)
    with settings(host_string=compute, password=get_env_passwords(compute)):
        get_name = "ifconfig -a | grep -B1 %s | cut -d' ' -f1" % compute_ip
        host_intf = sudo(get_name).strip()
        if host_intf == 'br0':
            get_hw_addr = "ifconfig br0 | grep 'HWaddr' | awk '{print $5}'"
            hw_addr = sudo(get_hw_addr).strip()
            get_name = "ifconfig -a | grep '%s' | awk '{print $1}'" % hw_addr
            host_intf_list = sudo(get_name).strip().split('\n')
            host_intf_list = map(str.strip, host_intf_list)
            host_intf_list.remove('br0')
            host_intf = host_intf_list[0]
    return host_intf

def get_vm_hosts():
    """Identifies the list of VM's
    """
    if 'vms' in env.keys():
        return env.vms.keys()
    else:
        return []

@task
#@parallel
@hosts(get_vm_hosts())
def setup_vtb():
    """Setup virtual testbed with inputs from testbed.py."""
    vm_hostname = hstr_to_ip(env.host_string)
    compute_host = env.vms[env.host_string]['compute']
    # build_template
    try:
        distro = env.ostypes[env.host_string]
        vm = importlib.import_module(
         'fabfile.contraillabs.vtb.templates.%s_vm_template' % distro)
    except ImportError:
        vm = importlib.import_module('templates.%s_vm_template' % distro)
    vm_config = vm.template.safe_substitute({
         '__name__' : vm_hostname,
         '__host_interface__' : get_compute_host_intf(compute_host),
         '__bridge_interface__' : 'br0',
         '__ipaddress__' : env.vms[env.host_string]['private_ip'],
    })

    vm_ini_file = '%s.ini' % vm_hostname
    with open(vm_ini_file, 'w+') as fd:
        fd.write(vm_config)

    vmi = execute('create_vm', compute_host, vm_ini_file)['<local-only>']
    if 'eth1' in vmi.keys():
        testbed = 'fabfile/testbeds/testbed.py'
        local("sed -i 's/%s/root@%s/g' %s" % (env.host_string,
                                              vmi['eth0'], testbed))

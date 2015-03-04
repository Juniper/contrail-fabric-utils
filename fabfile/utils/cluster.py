import logging as LOG
import paramiko

from fabric.api import env, settings, run

from fabos import detect_ostype, get_release, get_build
from fabfile.config import *

def ssh(host, user, passwd, log=LOG):
    """ SSH to any host.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=passwd)
    return ssh
# end ssh 
         
def execute_cmd(session, cmd, log=LOG):
    """Executing long running commands in background has issues
    So implemeted this to execute the command.
    """
    log.debug("Executing command: %s" % cmd)
    stdin, stdout, stderr = session.exec_command(cmd)
# end execute_cmd

def execute_cmd_out(session, cmd, log=LOG):
    """Executing long running commands in background through fabric has issues
    So implemeted this to execute the command.
    """
    stdin, stdout, stderr = session.exec_command(cmd)
    out = None
    err = None
    out = stdout.read()
    err = stderr.read()
        #log.debug("STDERR: %s", err)
    return (out, err)
# end execute_cmd_out

def get_orchestrator():
    return getattr(env, 'orchestrator', 'openstack')

def is_lbaas_enabled():
    if 'enable_lbaas' not in env.keys():
        return False
    else:
        return env.enable_lbaas

def get_vgw_details(compute_host_string):
    # Check and collect the VGW details for given compute host
    set_vgw = False
    vgw_intf_list = []
    public_subnet = []
    public_vn_name = []
    gateway_routes = []
    vgw_details = (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list)
    if ('vgw' not in env.roledefs or
        compute_host_string not in env.roledefs['vgw']):
        return vgw_details

    set_vgw = True
    vgw_intf_list = env.vgw[compute_host_string].keys()
    for vgw_intf in vgw_intf_list:
        public_subnet.append(env.vgw[compute_host_string][vgw_intf]['ipam-subnets'])
        public_vn_name.append(env.vgw[compute_host_string][vgw_intf]['vn'])
        if 'gateway-routes' in env.vgw[compute_host_string][vgw_intf].keys():
            gateway_routes.append(env.vgw[compute_host_string][vgw_intf]['gateway-routes'])

    vgw_details = (set_vgw, gateway_routes, public_subnet, public_vn_name, vgw_intf_list)
    return vgw_details
def get_vmware_details(compute_host_string):
    esxi_data = {}
    vmware = False
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if esxi_info:
        for host in esxi_info.keys():
            esxi_data = esxi_info[host]
            if (esxi_data['contrail_vm']['host'] == compute_host_string):
                if get_orchestrator() == 'openstack':
                    vmware = True
                break
    return (vmware, esxi_data)

def get_esxi_ssl_thumbprint(esxi_data):
    ssh_session = ssh(esxi_data['ip'], esxi_data['username'], esxi_data['password'])
    get_ssl_thumbprint = ("openssl x509 -in /etc/vmware/ssl/rui.crt -fingerprint -sha1 -noout")
    out, err = execute_cmd_out(ssh_session, get_ssl_thumbprint)
    out = out.split()
    out = out[1].split('=')
    ssl_thumbprint = out[1]
    print 'ssl thumbprint of the ESXi host %s is %s' % (esxi_data['ip'], ssl_thumbprint)
    return (ssl_thumbprint)

def get_nodes_to_upgrade_pkg(package, os_type, *args, **kwargs):
    """get the list of nodes in which th given package needs to be upgraded"""
    nodes = []
    version = kwargs.get('version', None)
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            act_os_type = detect_ostype()
            if act_os_type == os_type:
                installed = run("dpkg -l | grep %s" % package)
                if not installed:
                    nodes.append(host_string)
                elif (version and
                      version != '%s-%s' %
                         (get_release(package), get_build(package))):
                    nodes.append(host_string)
                else:
                    print 'Required package %s installed. Skipping!' % package
            else:
                raise RuntimeError('Actual OS Type (%s) != Expected OS Type (%s)'
                                    'Aborting!' % (act_os_type, os_type))
    return nodes

def reboot_nodes(*args):
    """reboots the given nodes"""
    for host_string in args:
        with settings(host_string=host_string):
            print "Rebooting (%s) to boot with new kernel version" % host_string
            try:
                sudo('reboot --force', timeout=3)
            except CommandTimeout:
                pass

def get_tsn_nodes():
    """Identifies the list of nodes to be provisioned as
       tsn nodes.
    """
    try:
        return env.roledefs['tsn']
    except KeyError:
        return []

def get_toragent_nodes():
    """Identifies the list of nodes to be provisioned as
       toragent nodes.
    """
    try:
        return env.roledefs['toragent']
    except KeyError:
        return []

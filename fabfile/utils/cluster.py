from distutils.version import LooseVersion

from fabric.api import env, settings, run

from fabos import detect_ostype, get_release, get_build, get_openstack_sku
from fabfile.config import *
from fabfile.utils.config import get_value
from fabfile.utils.interface import get_data_ip
from collections import OrderedDict

def get_all_hostnames():
    if isinstance(env.hostnames.get('all', None), list):
        # Maintaining backward compatability with old testbed.py
        hostnames = env.hostnames['all']
    else:
        hostnames = []
        for host in env.roledefs['all']:
            # Return hostnames in the same order in which the 'all'
            # role is defined.
            hostnames.append(env.hostnames[host])
    return hostnames


def get_hostname(host_string):
    if isinstance(env.hostnames.get('all', None), list):
        # Maintaining backward compatability with old testbed.py
        hostnames = dict(zip(env.roledefs['all'], env.hostnames['all']))
    else:
        hostnames = env.hostnames
    return hostnames[host_string]


def get_orchestrator():
    return getattr(env, 'orchestrator', 'openstack')


def get_mode(compute_host):
    mode = get_orchestrator()
    esxi_info = getattr(testbed, 'esxi_hosts', None)

    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return

    if esxi_info:
        for host in esxi_info.keys():
            esxi_data = esxi_info[host]
            if 'contrail_vm' not in esxi_data:
                continue #For vcenter gateway 'contrail_vm' not present in testbed.py
            data = esxi_data['contrail_vm']
            if (esxi_data['contrail_vm']['host'] == compute_host):
                if 'mode' in data.keys():
                   mode = esxi_data['contrail_vm']['mode']
    return mode

def is_lbaas_enabled():
    if 'enable_lbaas' not in env.keys():
        return False
    else:
        return env.enable_lbaas

def get_sriov_details(compute_host_string):

    sriov_string = ""
    if 'sriov' not in env.keys():
        return sriov_string

    if compute_host_string not in env.sriov:
        return sriov_string

    intf_list = env.sriov[compute_host_string]
    for intf in intf_list:
        if 'interface' in intf:
            if not intf.get('VF'):
                continue
            if not intf.get('physnets'):
                continue
            if not len(intf['physnets']):
                continue
            if sriov_string:
                sriov_string += ","
            sriov_string += intf['interface'] + ":" + str(intf['VF']) + ":"
            for phynet in intf['physnets']:
                sriov_string += phynet
                if intf['physnets'][-1] != phynet:
                    sriov_string += "%"
            
    return sriov_string

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

def get_qos_details(compute_host_string):
    set_qos = False
    default_hw_queue = False
    qos_logical_queue = []
    queue_id = []
    qos_details = (set_qos, qos_logical_queue, queue_id, default_hw_queue)
    qos_info = getattr(env, 'qos', None)
    if qos_info:
        if( compute_host_string not in qos_info.keys()):
            return qos_details
    else:
        return qos_details

    set_qos = True
    qos_info_compute = qos_info[compute_host_string]
    for nic_queue in qos_info_compute:
        if 'default' not in nic_queue.keys():
            qos_logical_queue.append(str(nic_queue['logical_queue']).strip('[]').replace(" ",""))
            queue_id.append(nic_queue['hardware_q_id'])
        else:
           default_nic_queue = nic_queue
           default_hw_queue = True
    if default_hw_queue:
        if 'logical_queue' in default_nic_queue.keys():
            qos_logical_queue.append(str(default_nic_queue['logical_queue']).strip('[]').replace(" ",""))
        queue_id.append(default_nic_queue['hardware_q_id'])

    qos_details = (set_qos, qos_logical_queue, queue_id, default_hw_queue)
    return qos_details

def get_priority_group_details(compute_host_string):
    set_priority = False
    priority_id = []
    priority_bandwidth = []
    priority_scheduling = []
    priority_details = (set_priority, priority_id, priority_bandwidth, priority_scheduling)
    priority_info = getattr(env, 'qos_niantic', None)
    if priority_info:
        if (compute_host_string not in priority_info.keys()):
            return priority_details
    else:
        return priority_details

    set_priority = True
    priority_info_compute = priority_info[compute_host_string]
    for priority in priority_info_compute:
        priority_id.append(priority['priority_id'])
        priority_scheduling.append(priority['scheduling'])
        if priority['scheduling'] != 'strict':
            priority_bandwidth.append(priority['bandwidth'])
        else:
            priority_bandwidth.append('0')

    priority_details = (set_priority, priority_id, priority_bandwidth, priority_scheduling)
    return priority_details

def get_qos_nodes():
    """Identifies the list of nodes to be provisioned for
       Qos in testbed.py.
    """
    qos_info = getattr(env, 'qos', None)
    if qos_info:
        return qos_info.keys()
    else:
        return []

def get_qos_niantic_nodes():
    """Identifies the list of nodes to be provisioned for
       Qos on niantic nic with priority group configuration in testbed.py .
    """
    qos_niantic_info = getattr(env, 'qos_niantic', None)
    if qos_niantic_info:
        return qos_niantic_info.keys()
    else:
        return []

def get_compute_as_gateway_list():
    gateway_server_ip_list = []
    gateway_mode_info = getattr(env, 'compute_as_gateway_mode', None)
    if gateway_mode_info:
        for host in gateway_mode_info.keys():
            if( gateway_mode_info[host] == 'server' ):
                gateway_server_ip_list.append(get_data_ip(host)[0])
    return gateway_server_ip_list

def get_vmware_details(compute_host_string):
    esxi_data = {}
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if esxi_info:
        for host in esxi_info.keys():
            esxi_data = esxi_info[host]
            if 'contrail_vm' not in esxi_data:
                continue #For vcenter gateway contrail_vm not present in testbed.py
            data = esxi_data['contrail_vm']
            if (esxi_data['contrail_vm']['host'] == compute_host_string):
                 return esxi_data
            else:
                 continue
    return None

def get_vcenter_datacenter_mtu(vcenter_server_name):
    vcenter_data = {}
    datacenter_mtu = 1500
    vcenter_info = getattr(env, 'vcenter_servers', None)
    if vcenter_server_name in vcenter_info.keys():
        vcenter_server = vcenter_info[vcenter_server_name]
        if 'datacenter_mtu' in vcenter_server.keys():
            datacenter_mtu = vcenter_server['datacenter_mtu']

    return datacenter_mtu

def get_esxi_ssl_thumbprint(esxi_data):
    host_string = '%s@%s' %(esxi_data['username'], esxi_data['ip'])
    with settings(host_string = host_string, password = esxi_data['password'],
                    warn_only = True, shell = '/bin/sh -l -c'):
          # Do not change to sudo, It should be run/sudo will not work in eski hosts.
          out = run('openssl x509 -in /etc/vmware/ssl/rui.crt -fingerprint -sha1 -noout')
          out = out.split()
          out = out[7].split('=')
          ssl_thumbprint = out[1]
          print 'ssl thumbprint of the ESXi host %s is %s' % (esxi_data['ip'], ssl_thumbprint)
    return ssl_thumbprint

def get_esxi_vms_and_hosts(esxi_info, vcenter_server, host_list, compute_list, password_list):
    hosts = []
    vms = []
    for host in host_list:
         with settings(host=host):
               if host in esxi_info.keys():
                   esxi_data = esxi_info[host]
                   vm_name = "ContrailVM"
                   ssl_thumbprint = get_esxi_ssl_thumbprint(esxi_data)
                   esx_list=esxi_data['ip'],esxi_data['username'],esxi_data['password'],ssl_thumbprint,esxi_data['cluster']
                   hosts.append(esx_list)
                   modified_vm_name = vm_name+"-"+esxi_data['datacenter']+"-"+esxi_data['ip']
                   for host_string in compute_list:
                       try: 
                           if host_string == esxi_data['contrail_vm']['host']:
                               break
                       except Exception as e:#Handling exception in case 
                           print '%s'%e      #contrail_vm not present(vcenter gateway) 
                   password  = password_list[host_string]
                   vm_info_list = modified_vm_name, host_string, password
                   vms.append(vm_info_list)
               else:
                   print 'Info: esxi_hosts block does not have the esxi host.Exiting'
                   return
    return (hosts,vms)

def get_vcenter_datacenters(server):
    datacenters = []
    for dc in server['datacenters'].keys():
         datacenters.append(dc)

    return datacenters 

def get_vcenter_clusters(datacenter):
    clusters = []
    for dvs in datacenter['dv_switches'].keys():
         dvs_info = datacenter['dv_switches'][dvs]
         openstack_sku = get_openstack_sku(use_install_repo=True)
         if openstack_sku in ['mitaka', 'newton']:
             if len(dvs_info['clusters']) > 1:
                 print 'Error: Multiple clusters per datacenter not supported'
                 return None
         for cluster in dvs_info['clusters']:
              clusters.append(cluster)

    return clusters

def get_vcenter_dvswitches(datacenter):
    dv_switches = []
    for dvs in datacenter['dv_switches'].keys():
         dvs_info = datacenter['dv_switches'][dvs]
         dv_switch_name = dvs
         dv_switch_version = dvs_info['dv_switch_version']
         dv_portgroup_name = dvs_info['dv_port_group']['dv_portgroup_name']
         dv_portgroup_num_ports = dvs_info['dv_port_group']['number_of_ports']

         dvs_info_list = dv_switch_name, dv_switch_version, dv_portgroup_name, dv_portgroup_num_ports
         dv_switches.append(dvs_info_list)

    return dv_switches 

def get_vcenter_compute_nodes(datacenter):
    vcenter_compute_nodes = []
    for dvs in datacenter['dv_switches'].keys():
         dvs_info = datacenter['dv_switches'][dvs]
         vcenter_compute_nodes.append(dvs_info['vcenter_compute'])

    return vcenter_compute_nodes 

def is_dv_switch_fab_configured():
    dv_switch_fab = False
    vcenter_info = getattr(env, 'vcenter_servers', None)
    for v in vcenter_info.keys():
        vcenter_server = vcenter_info[v]
        for dc in vcenter_server['datacenters']:
            dc_info = vcenter_server['datacenters'][dc]
            dvs = dc_info['dv_switches']
            if 'dv_switch_fab' in dvs.keys():
                dv_switch_fab = True

    return dv_switch_fab

def create_esxi_vrouter_map_file(vcenter_server_name, vcenter_server, host_string):
    #create the static esxi:vrouter map file
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return

    esxi_hosts = []
    for host in esxi_info.keys():
        if esxi_info[host]['vcenter_server'] is vcenter_server_name:
           esxi_hosts.append(host)

    with settings(host_string=host_string, warn_only=True):
         tmp_fname = "/tmp/ESXiToVRouterIp-%s" %(host_string)

         # Get all clusters managed by this server.
         for dc in vcenter_server['datacenters'].keys():
              dc_info = vcenter_server['datacenters'][dc]
              clusters = get_vcenter_clusters(dc_info)
              if not clusters:
                  print 'Error: clusters not defined'

         for esxi_host in esxi_hosts:
             if esxi_info[esxi_host]['cluster'] in clusters:
                esxi_ip = esxi_info[esxi_host]['ip']
                vrouter_ip_string = esxi_info[esxi_host]['contrail_vm']['host']
                vrouter_ip = vrouter_ip_string.split('@')[1]
                local("echo '%s:%s' >> %s" %(esxi_ip, vrouter_ip, tmp_fname))
         put(tmp_fname, "/etc/contrail/ESXiToVRouterIp.map", use_sudo=True)
         local("rm %s" %(tmp_fname))

def update_esxi_vrouter_map_file(esxi_host):
    #update the static esxi:vrouter map file
    esxi_info = getattr(testbed, 'esxi_hosts', None)
    if not esxi_info:
        print 'Info: esxi_hosts block is not defined in testbed file. Exiting'
        return

    esxi_ip = esxi_info[esxi_host]['ip']
    vrouter_ip_string = esxi_info[esxi_host]['contrail_vm']['host']
    vrouter_ip = vrouter_ip_string.split('@')[1]
    map_file = open('/etc/contrail/ESXiToVRouterIp.map', 'a')
    map_file.write('%s:%s\n' %(esxi_ip, vrouter_ip))
    map_file.close()

def get_nodes_to_upgrade_pkg(package, os_type, *args, **kwargs):
    """get the list of nodes in which th given package needs to be upgraded"""
    nodes = []
    version = kwargs.get('version', None)
    for host_string in args:
        with settings(host_string=host_string, warn_only=True):
            if os_type in ['ubuntu']:
                installed = sudo("dpkg -l | grep %s" % package)
            elif os_type in ['centos', 'redhat', 'centoslinux']:
                installed = sudo("rpm -qa | grep %s" % package)
            else:
                raise RuntimeError('Unsupported OS type!')

            if not installed:
                nodes.append(host_string)
            elif (version and
                  version != '%s-%s' %
                     (get_release(package), get_build(package))):
                nodes.append(host_string)
            else:
                print 'Required package %s installed. Skipping!' % package
    return nodes

def get_package_installed_info(package, os_type, *nodes):
    """Check if given package is installed in nodes and return
       installation info
    """
    pkg_status = {'installed': [], 'not_installed': []}
    for host_string in nodes:
        with settings(host_string=host_string, warn_only=True):
            if os_type.lower() in ['ubuntu']:
               cmd = 'dpkg -l %s' % package
            elif os_type.lower() in ['centos', 'redhat', 'fedora', 'centoslinux']:
                cmd = 'rpm -q %s' % package
            else:
                raise RuntimeError('[%s]: Unsupported OS Type (%s)' % (host_string, os_type))
            if sudo(cmd).succeeded:
                pkg_status['installed'].append(host_string)
                continue
        pkg_status['not_installed'].append(host_string)
    return pkg_status

def reboot_nodes(*args):
    """reboots the given nodes"""
    for host_string in args:
        with settings(host_string=host_string):
            os_type =  detect_ostype()
            print "Rebooting (%s) to boot with new kernel version" % host_string
            try:
                if os_type.lower() in ['ubuntu']:
                    sudo('sync; reboot --force', timeout=3)
                else:
                    sudo('sleep 5; shutdown -r now', timeout=3)
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

def get_ntp_server():
    return getattr(env, 'ntp_server', None)

def get_metadata_secret():
    """ Retrieves metadata secret
        1. if metadata secret is supplied in testbed, retrieve its value from testbed
        2. if not defined in testbed, depending on orchestrator, retrieve it from
           the first orchestrator node
    """

    metadata_secret = None
    orch = get_orchestrator()
    if orch.lower() == 'openstack':
        openstack_host = env.roledefs['openstack'][0]

        # Use metadata_secret provided in testbed. If not available
        # retrieve metadata secret from openstack node
        metadata_secret = getattr(testbed,
                                  'neutron_metadata_proxy_shared_secret',
                                  None)

        if not metadata_secret:
            with settings(host_string=openstack_host):
                ostype = detect_ostype()
                # For Juno, use service_metadata_proxy metadata_proxy_shared_secret
                # from neutron section in /etc/nova/nova.conf
                if ostype.lower() in ['centos', 'redhat', 'centoslinux']:
                    api_version = sudo("rpm -q --queryformat='%{VERSION}' openstack-nova-api")
                    is_juno_or_higher = LooseVersion(api_version) >= LooseVersion('2014.2.2')
                elif ostype.lower() in ['ubuntu']:
                    api_version = sudo("dpkg-query -W -f='${VERSION}' nova-api")
                    is_juno_or_higher = LooseVersion(api_version) >= LooseVersion('2014.2.2')
                else:
                    raise RuntimeError("Unknown ostype (%s)" % ostype)

                if is_juno_or_higher:
                    status, secret = get_value('/etc/nova/nova.conf',
                                               'neutron',
                                               'service_metadata_proxy',
                                               'metadata_proxy_shared_secret')
                else:
                    status, secret = get_value('/etc/nova/nova.conf',
                                               'DEFAULT',
                                               'service_neutron_metadata_proxy',
                                               'neutron_metadata_proxy_shared_secret')
            metadata_secret = secret if status == 'True' else None
    else:
        print "WARNING get_metadata_secret: Orchestrator(%s) is not supported" % orch
    return metadata_secret

def is_contrail_node(node):
    '''Assuming that all contrail nodes are installed with
       package - contrail-setup, returns True if the package is installed in the node
    '''
    package_info = ''
    with settings(host_string=node, warn_only=True):
        package_info = get_build('contrail-setup')
    return True if package_info else False


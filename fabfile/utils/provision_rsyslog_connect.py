#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import sys
import argparse
import cfgparse
import ConfigParser
import socket

from vnc_api.vnc_api import *
from vnc_api.gen.resource_xsd import RouteType
from vnc_api.gen.resource_xsd import RouteTableType
from vnc_api.gen.resource_client import InterfaceRouteTable
from fabfile.config import *
from fabric.operations import put, get
from time import sleep


class SetupRsyslogConnections(object):

    def __init__(self, args_str=None):
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)
        self.name = 'SetupRsyslogConnections'
        self.collector_conf_file_path = '/etc/contrail/'
        self.collector_conf_file = self.collector_conf_file_path + \
            'contrail-collector.conf'
        self.local_conf_file = '/tmp/collector.conf' + "." + self.name
        self.local_copy = '/tmp/contrail-collector.conf'
        self.rsyslog_conf_file = '/etc/rsyslog.conf'
        self.sed_work_dir = '$WorkDirectory \/var\/tmp'
        self.work_dir = '$WorkDirectory /var/tmp'
        self.q_file_name = '$ActionQueueFileName fwdRule1'
        self.disk_space = '$ActionQueueMaxDiskSpace 1g'
        self.save_q = '$ActionQueueSaveOnShutdown on'
        self.q_type = '$ActionQueueType LinkedList'
        self.resume_retry_count = '$ActionResumeRetryCount -1'

        if self._args.cleanup == 'True':
            self.cleanup_rsyslog_client_server_configs(
                self._args.collector_ips,
                self._args.all_node_ips)
        else:
            self.setup_rsyslog_client_server_configs(
                self._args.rsyslog_port_number,
                self._args.rsyslog_transport_protocol,
                self._args.rsyslog_connection_mode,
                self._args.collector_ips,
                self._args.all_node_ips)

    def round_robin_collector_ip_assignment(self, all_node_ips, collector_ips):
        '''
        From the node IP and collector IPs create a dictionary to do a static mapping of remote nodes to connect to collectors
        which can be refered to by rsyslog clients. The connection principle followed here for remote clients is on a round robin
        basis of servers.
        '''
        mapping_dict = {}
        ind = -1
        for node_ip in all_node_ips:
            flag = 0
            for coll_ip in collector_ips:
                if node_ip == coll_ip:
                    mapping_dict[node_ip] = coll_ip
                    flag = 1
                    break
            if flag != 1:
                ind += 1
                if ind == len(collector_ips):
                    ind = 0
                mapping_dict[node_ip] = collector_ips[ind]

        return mapping_dict
    # end of round_robin_collector_ip_assignment

    def configure_syslog_listening_port_on_server(self, port, collector_ips):
        for each_node in collector_ips:
            username = 'root'
            pswd = env.passwords['root@' + each_node]
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):
                get(self.collector_conf_file, self.local_conf_file)
            config = cfgparse.ConfigParser()
            conf_file = config.add_file(self.local_conf_file)
            syslog_opt = config.add_option(
                'syslog_port',
                type='int',
                keys='DEFAULT')
            syslog_opt.set(port, conf_file)
            with open(self.local_copy, 'wb') as file_to_update:
                conf_file.write(file_to_update)
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):
                put(self.local_copy, self.collector_conf_file_path)
                # Restart vizd after change.
                cmd = "service contrail-collector restart"
                run('%s' % (cmd), pty=True)
    # end configure_syslog_listening_port_on_server

    def cleanup_rsyslog_client_server_configs(
            self,
            collector_ips,
            all_node_ips):
        # Delete the listening port on server(vizd) side if configured and
        # restart collector service.
        listen_port = -1
        for each_node in collector_ips:
            username = 'root'
            pswd = env.passwords['root@' + each_node]
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):
                get(self.collector_conf_file, self.local_conf_file)
            config = cfgparse.ConfigParser()
            conf_file = config.add_file(self.local_conf_file)
            syslog_opt = config.add_option(
                'syslog_port',
                type='int',
                keys='DEFAULT')
            syslog_opt.set(listen_port, conf_file)
            with open(self.local_copy, 'wb') as file_to_update:
                conf_file.write(file_to_update)
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):
                put(self.local_copy, self.collector_conf_file_path)
                # Restart vizd after change.
                cmd = "service contrail-collector restart"
                run('%s' % (cmd), pty=True)

        # Delete the client side(rsyslogd) iconfigurations and restart rsyslogd
        # service on every node.
        for each_node in all_node_ips:
            username = 'root'
            pswd = env.passwords['root@' + each_node]
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):
                # Delete Queue file name in rsyslog.conf
                cmd = "sed -i '/$ActionQueueFileName/d' " + \
                    self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # Delete Max Disk Space for remote logging packets in
                # rsyslog.conf
                cmd = "sed -i '/$ActionQueueMaxDiskSpace/d' " + \
                    self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # Delete Queue save on shutdown
                cmd = "sed -i '/$ActionQueueSaveOnShutdown/d' " + \
                    self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # Delete Queue type
                cmd = "sed -i '/$ActionQueueType/d' " + self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # Delete Connection resume retry count
                cmd = "sed -i '/$ActionResumeRetryCount/d' " + \
                    self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # Delete rsyslog client-server connection details
                cmd = "sed -i '/@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}/d' " + \
                    self.rsyslog_conf_file
                run('%s' % (cmd), pty=True)

                # restart rsyslog service
                cmd = "service rsyslog restart"
                run('%s' % (cmd), pty=True)

    # end of cleanup_rsyslog_client_server_configs

    def setup_rsyslog_client_server_configs(
            self,
            port,
            protocol,
            collector_connection,
            collector_ips,
            all_node_ips):

        # Configure the listening port on server(vizd) side if its not already
        # listening on the expected port.
        if collector_connection == 'static':
            self.configure_syslog_listening_port_on_server(
                port, 
                [collector_ips[0]])
            connect_map_dict = {}
            for node_ip in all_node_ips:
                connect_map_dict[node_ip] = collector_ips[0]
        else:
            self.configure_syslog_listening_port_on_server(port, collector_ips)
            # Create a dictionary of connection mapping for remote clients to vizd servers based on round robin algorithm.
            # connect_map_dict = {<node-ip-address> : <collector-ip-address>}
            connect_map_dict = 0
            connect_map_dict = self.round_robin_collector_ip_assignment(
                all_node_ips,
                collector_ips)

        # Configure the client side(rsyslogd) to send logs to the various
        # servers(vizd/collectors) present in the setup.
        for each_node in all_node_ips:
            username = 'root'
            pswd = env.passwords['root@' + each_node]
            with settings(host_string='%s@%s' % (username, each_node), password=pswd,
                          warn_only=True, abort_on_prompts=False):

                # update Working Directory in rsyslog.conf
                cmd = "grep 'WorkDirectory' " + self.rsyslog_conf_file + \
                      " && sed -i '/WorkDirectory/c\\\\" + self.sed_work_dir + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.work_dir + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update Queue file name in rsyslog.conf
                cmd = "grep 'ActionQueueFileName' " + self.rsyslog_conf_file + \
                      " && sed -i '/ActionQueueFileName/c\\\\" + self.q_file_name + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.q_file_name + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update Max Disk Space for remote logging packets in
                # rsyslog.conf
                cmd = "grep 'ActionQueueMaxDiskSpace' " + self.rsyslog_conf_file + \
                      " && sed -i '/ActionQueueMaxDiskSpace/c\\\\" + self.disk_space + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.disk_space + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update Queue save on shutdown
                cmd = "grep 'ActionQueueSaveOnShutdown' " + self.rsyslog_conf_file + \
                      " && sed -i '/ActionQueueSaveOnShutdown/c\\\\" + self.save_q + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.save_q + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update Queue type
                cmd = "grep 'ActionQueueType' " + self.rsyslog_conf_file + \
                      " && sed -i '/ActionQueueType/c\\\\" + self.q_type + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.q_type + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update Connection resume retry count
                cmd = "grep 'ActionResumeRetryCount' " + self.rsyslog_conf_file + \
                      " && sed -i '/ActionResumeRetryCount/c\\\\" + self.resume_retry_count + \
                      "' " + self.rsyslog_conf_file + " || echo '" + self.resume_retry_count + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # update rsyslog client-server connection details
                if protocol == 'tcp':
                    protocol = '@@'
                else:
                    protocol = '@'
                ip_address_of_server = '0.0.0.0'
                loop_back_ip = '127.0.0.1'
                for each_ip in collector_ips:
                    if each_node == each_ip:
                        ip_address_of_server = loop_back_ip

                # if collector is remote use round robin to assign collector ip
                # to the clients.
                if ip_address_of_server != loop_back_ip:
                    # Assign ip address of server as indicated in the
                    # dictionary defining client-server connections.
                    ip_address_of_server = connect_map_dict[each_node]

                connection_string = '*.* ' + protocol + \
                    ip_address_of_server + ':' + str(port)
                cmd = "grep '@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}' " + \
                      self.rsyslog_conf_file + " && sed -i '/@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}/c\\" \
                      + str(connection_string) + "' " + self.rsyslog_conf_file + " || echo '" + str(connection_string) + \
                      "' >> " + self.rsyslog_conf_file
                output = run('%s' % (cmd), pty=True)

                # restart rsyslog service
                cmd = "service rsyslog restart"
                run('%s' % (cmd), pty=True)

    # end of setup_rsyslog_client_server_configs

    def _parse_args(self, args_str):
        '''
        Eg. python provision_rsyslog_connect.py
                                        --rsyslog_port_number 1234
                                        --rsyslog_transport_protocol <tcp/udp>
                                        --rsyslog_connection_mode <static/dynamic>
                                        --collector_ips 1.1.1.1 2.2.2.2 3.3.3.3
                                        --all_node_ips 1.1.1.1 2.2.2.2 3.3.3.3 4.4.4.4
                                        --cleanup True/False
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        global_defaults = {
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            global_defaults.update(dict(config.items("GLOBAL")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        all_defaults = {'global': global_defaults}
        parser.set_defaults(**all_defaults)
        parser.add_argument(
            "--rsyslog_port_number",
            help="Port number on which the rsyslog server/collector and rsyslog client should connect",
            type=int)
        parser.add_argument(
            "--rsyslog_transport_protocol",
            help="Rsyslog transport protocol",
            type=str)
        parser.add_argument(
            "--rsyslog_connection_mode",
            help="Rsyslog client server connection mode",
            type=str)
        parser.add_argument(
            "--collector_ips",
            help="IP Address of the collector nodes",
            nargs='+',
            type=str)
        parser.add_argument(
            "--all_node_ips",
            help="IP Address of all the nodes in the setup",
            nargs='+',
            type=str)
        parser.add_argument(
            "--cleanup",
            help="Cleanup routine to be called or not True/False",
            type=str)
        self._args = parser.parse_args(remaining_argv)
    # end _parse_args

# end class SetupRsyslogConnections


def main(args_str=None):
    SetupRsyslogConnections(args_str)
# end main

if __name__ == "__main__":
    main()

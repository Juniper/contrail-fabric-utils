#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import sys
import os
import argparse
import ConfigParser
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
                self._args.mode)
        else:
            self.setup_rsyslog_client_server_configs(
                self._args.rsyslog_port_number,
                self._args.rsyslog_transport_protocol,
                self._args.mode,
                self._args.collector_ip)

    def configure_syslog_listening_port_on_server(self, port, collector_ips):
        for each_node in collector_ips:
            cmd = "cp -f " + self.collector_conf_file + \
                " " + self.local_conf_file
            os.system('%s' % (cmd))
            cmd = "sed -i 's/^ *//g' %s" %(self.local_conf_file)
            os.system('%s' % (cmd))
            config = ConfigParser.ConfigParser()
            config.read(self.local_conf_file)
            config.set('DEFAULT', 'syslog_port', port)
            with open(self.local_copy, 'wb') as file_to_update:
                config.write(file_to_update)
            cmd = "cp -f " + self.local_copy + \
                " " + self.collector_conf_file_path
            os.system('%s' % (cmd))
            # Restart vizd after change.
            cmd = "service contrail-collector restart"
            os.system('%s' % (cmd))
    # end configure_syslog_listening_port_on_server

    def cleanup_rsyslog_client_server_configs(
            self,
            mode):
        # Delete the listening port on server(vizd) side if configured and
        # restart collector service.
        if mode == 'receiver':
            listen_port = -1
            cmd = "cp -f " + self.collector_conf_file + \
                " " + self.local_conf_file
            os.system('%s' % (cmd))
            cmd = "sed -i 's/^ *//g' %s" %(self.local_conf_file)
            os.system('%s' % (cmd))
            config = ConfigParser.ConfigParser()
            config.read(self.local_conf_file)
            config.set('DEFAULT', 'syslog_port', listen_port)
            with open(self.local_copy, 'wb') as file_to_update:
                config.write(file_to_update)
            cmd = "cp -f " + self.local_copy + \
                " " + self.collector_conf_file_path
            os.system('%s' % (cmd))
            # Restart vizd after change.
            cmd = "service contrail-collector restart"
            os.system('%s' % (cmd))

        # Delete the client side(rsyslogd) iconfigurations and restart rsyslogd
        # service on every node.

        # Delete Queue file name in rsyslog.conf
        cmd = "sed -i '/$ActionQueueFileName/d' " + \
            self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # Delete Max Disk Space for remote logging packets in
        # rsyslog.conf
        cmd = "sed -i '/$ActionQueueMaxDiskSpace/d' " + \
            self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # Delete Queue save on shutdown
        cmd = "sed -i '/$ActionQueueSaveOnShutdown/d' " + \
            self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # Delete Queue type
        cmd = "sed -i '/$ActionQueueType/d' " + self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # Delete Connection resume retry count
        cmd = "sed -i '/$ActionResumeRetryCount/d' " + \
            self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # Delete rsyslog client-server connection details
        cmd = "sed -i '/@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}/d' " + \
            self.rsyslog_conf_file
        os.system('%s' % (cmd))

        # restart rsyslog service
        cmd = "service rsyslog restart"
        os.system('%s' % (cmd))

    # end of cleanup_rsyslog_client_server_configs

    def setup_rsyslog_client_server_configs(
            self,
            port,
            protocol,
            mode,
            collector_ip):

        # Configure the listening port on server(vizd) side if its not already
        # listening on the expected port.
        if mode == 'receiver':
            self.configure_syslog_listening_port_on_server(
                port,
                [collector_ip])

        # Configure the client side(rsyslogd) to send logs to the various
        # servers(vizd/collectors) present in the setup.

        # update Working Directory in rsyslog.conf
        cmd = "grep 'WorkDirectory' " + self.rsyslog_conf_file + \
              " && sed -i '/WorkDirectory/c\\\\" + self.sed_work_dir + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.work_dir + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update Queue file name in rsyslog.conf
        cmd = "grep 'ActionQueueFileName' " + self.rsyslog_conf_file + \
              " && sed -i '/ActionQueueFileName/c\\\\" + self.q_file_name + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.q_file_name + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update Max Disk Space for remote logging packets in
        # rsyslog.conf
        cmd = "grep 'ActionQueueMaxDiskSpace' " + self.rsyslog_conf_file + \
              " && sed -i '/ActionQueueMaxDiskSpace/c\\\\" + self.disk_space + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.disk_space + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update Queue save on shutdown
        cmd = "grep 'ActionQueueSaveOnShutdown' " + self.rsyslog_conf_file + \
              " && sed -i '/ActionQueueSaveOnShutdown/c\\\\" + self.save_q + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.save_q + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update Queue type
        cmd = "grep 'ActionQueueType' " + self.rsyslog_conf_file + \
              " && sed -i '/ActionQueueType/c\\\\" + self.q_type + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.q_type + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update Connection resume retry count
        cmd = "grep 'ActionResumeRetryCount' " + self.rsyslog_conf_file + \
              " && sed -i '/ActionResumeRetryCount/c\\\\" + self.resume_retry_count + \
              "' " + self.rsyslog_conf_file + " || echo '" + self.resume_retry_count + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # update rsyslog client-server connection details
        if protocol == 'tcp':
            protocol = '@@'
        else:
            protocol = '@'

        ip_address_of_server = collector_ip

        connection_string = '*.* ' + protocol + \
            ip_address_of_server + ':' + str(port)
        cmd = "grep '@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}' " + \
              self.rsyslog_conf_file + " && sed -i '/@\{1,2\}[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\:[0-9]\{1,5\}/c\\" \
              + str(connection_string) + "' " + self.rsyslog_conf_file + " || echo '" + str(connection_string) + \
              "' >> " + self.rsyslog_conf_file
        output = os.system('%s' % (cmd))

        # restart rsyslog service
        cmd = "service rsyslog restart"
        os.system('%s' % (cmd))

    # end of setup_rsyslog_client_server_configs

    def _parse_args(self, args_str):
        '''
        Eg. python provision_rsyslog_connect.py
                                        --rsyslog_port_number 1234
                                        --rsyslog_transport_protocol <tcp/udp>
                                        --mode <generator/receiver>
                                        --collector_ip 1.1.1.1
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
            "--mode",
            help="Syslog receiver and generator or only generator mode",
            type=str)
        parser.add_argument(
            "--collector_ip",
            help="IP Address of the collector node",
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

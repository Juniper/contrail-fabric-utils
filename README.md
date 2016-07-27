contrail-fabric-utils
=====================

# Contrail Fabric Utilites

This software is licensed under the Apache License, Version 2.0 (the "License");
you may not use this software except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

### Overview

The Contrail Fabric-utils repository contains the code for installing and setting up Contrail network virtualization solution.
All fabric tasks in this repository are driven by the input file ``fabfile/testbeds/testbed.py``, Example testbed.py files are at [fabfile/testbeds/testbed_singlebox_example.py](fabfile/testbeds/testbed_singlebox_example.py) and [fabfile/testbeds/testbed_multibox_example.py](fabfile/testbeds/testbed_multibox_example.py)

The Contrail provisioning code is available in a separate code repository (http://github.com/Juniper/contrail-provisioning).

### Install
Fabric tasks to install Contrail network virtualization solution in a cluster are located under ``fabfile/tasks/install.py``, It provides various fabric tasks to install specific cluster node with specific packages based on roles.

### Setup
Fabric tasks to setup Contrail network virtualization solution in a cluster are located under ``fabfile/tasks/setup.py``, It provides various fabric tasks to setup specific cluster node with specific components/services based on roles.

### Upgrade
Fabric tasks to upgrade Contrail network virtualization solution in a cluster are located under ``fabfile/tasks/upgrade.py``, It provides various fabric tasks to upgrade specific cluster node based on roles.

More specific information on fabric tasks to bringup a cluster with Contrail network virtualization solution is in ``README`` file.

### Filing Bugs
Use http://bugs.launchpad.net/juniperopenstack
It will be useful to include the fabric execution log file in the bug, log files will be created in the directory from where a fabric task is trrigered.

### Queries
Mail to
dev@lists.opencontrail.org,
users@lists.opencontrail.org

### IRC
opencontrail on freenode.net

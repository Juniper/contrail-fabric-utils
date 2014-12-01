import os

from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.tasks.storage.install import install_storage_compute_node
#from fabfile.tasks.storage.provision import setup_storage_node

@task
def add_storage_node(*args):
    """Adds one/more new storage node to the existing cluster."""
    for host_string in args:
        with settings(host_string=host_string):
            execute("create_storage_repo_node", env.host_string)
            execute("install_storage_compute_node", env.host_string)
    execute("setup_master_storage", "setup")

#@task
#def detach_storage_node(*args):
#    """Detaches one/more compute node from the existing cluster."""
#    TBD



from fabfile.config import testbed
from fabric.api import env

def is_lbaas_enabled():
    if 'enable_lbaas' not in env.keys():
        return False
    else:
        return env.enable_lbaas


import os
from time import sleep

from fabric.contrib.files import exists

from fabfile.config import *
from fabfile.utils.cluster import (get_keystone_certfile, get_keystone_keyfile,
                                   get_keystone_cafile, get_apiserver_certfile,
                                   get_apiserver_keyfile, get_apiserver_cafile)


@task
@EXECUTE_TASK
@roles('openstack')
def setup_keystone_ssl_certs():
    execute('setup_keystone_ssl_certs_node', env.host_string)


def setup_keystone_ssl_certs_node(*nodes):
    default_certfile = '/etc/keystone/ssl/certs/keystone.pem'
    default_keyfile = '/etc/keystone/ssl/private/keystone_key.pem'
    default_cafile = '/etc/keystone/ssl/certs/keystone_ca.pem'
    ssl_certs = ((get_keystone_certfile(), default_certfile),
                 (get_keystone_keyfile(), default_keyfile),
                 (get_keystone_cafile(), default_cafile))
    index = env.roledefs['openstack'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_password(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    if index == 1:
                        print "Creating keystone SSL certs in first openstack node"
                        sudo('create-keystone-ssl-certs.sh')
                    else:
                        openstack_host = env.roledefs['openstack'][0]
                        with settings(host_string=openstack_host,
                                      password=get_env_passwords(openstack_host)):
                            while not exists(ssl_cert, use_sudo=True):
                                print "Wait for SSL certs to be created in first openstack"
                                sleep(0.1)
                            print "Get SSL cert(%s) from first openstack" % ssl_cert
                            tmp_fname = os.path.join('/tmp', os.path.basename(ssl_cert))
                            get_as_sudo(ssl_cert, tmp_fname)
                        print "Copy to this(%s) openstack node" % env.host_string 
                        put(tmp_fname, ssl_cert, use_sudo=True)
                        os.remove(tmp_fname)
                elif os.path.isfile(ssl_cert): 
                    print "Certificate (%s) exists locally" % ssl_cert
                    put(ssl_cert, default, use_sudo=True)
                elif exists(ssl_cert, use_sudo=True): 
                    print "Certificate (%s) exists in openstack node" % ssl_cert
                    pass
                else:
                    raise RuntimeError("%s doesn't exists locally or in openstack node")


@task
@EXECUTE_TASK
@roles('cfgm')
def setup_apiserver_ssl_certs():
    execute('setup_apiserver_ssl_certs_node', env.host_string)


def setup_apiserver_ssl_certs_node(*nodes):
    default_certfile = '/etc/contrail/ssl/certs/apiserver.pem'
    default_keyfile = '/etc/contrail/ssl/private/apiserver_key.pem'
    default_cafile = '/etc/contrail/ssl/certs/apiserver_ca.pem'
    ssl_certs = ((get_apiserver_certfile(), default_certfile),
                 (get_apiserver_keyfile(), default_keyfile),
                 (get_apiserver_cafile(), default_cafile))
    index = env.roledefs['cfgm'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_password(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    if index == 1:
                        print "Creating apiserver SSL certs in first cfgm node"
                        sudo('create-api-ssl-certs.sh')
                    else:
                        cfgm_host = env.roledefs['cfgm'][0]
                        with settings(host_string=cfgm_host,
                                      password=get_env_passwords(cfgm_host)):
                            while not exists(ssl_cert, use_sudo=True):
                                print "Wait for SSL certs to be created in first cfgm"
                                sleep(0.1)
                            print "Get SSL cert(%s) from first cfgm" % ssl_cert
                            tmp_fname = os.path.join('/tmp', os.path.basename(ssl_cert))
                            get_as_sudo(ssl_cert, tmp_fname)
                        print "Copy to this(%s) cfgm node" % env.host_string 
                        put(tmp_fname, ssl_cert, use_sudo=True)
                        os.remove(tmp_fname)
                elif os.path.isfile(ssl_cert): 
                    print "Certificate (%s) exists locally" % ssl_cert
                    put(ssl_cert, default, use_sudo=True)
                elif exists(ssl_cert, use_sudo=True): 
                    print "Certificate (%s) exists in cfgm node" % ssl_cert
                else:
                    raise RuntimeError("%s doesn't exists locally or in cfgm node")


@task
@EXECUTE_TASK
@roles('cfgm')
def copy_keystone_ssl_certs_to_config():
    execute('copy_keystone_ssl_certs_to_config_node', env.host_string)


@task
def copy_keystone_ssl_certs_to_config_node(*nodes):
    ssl_certs = (get_keystone_certfile(),
                 get_keystone_keyfile(),
                 get_keystone_cafile())
    openstack_host = env.roledefs['openstack'][0]
    for node in nodes:
        with settings(host_string=node, password=get_env_password(node)):
            for ssl_cert, in ssl_certs:
                with settings(host_string=openstack_host,
                              password=get_env_passwords(openstack_host)):
                    tmp_fname = os.path.join('/tmp', os.path.basename(ssl_cert))
                    get_as_sudo(ssl_cert, tmp_fname)
                put(tmp_fname, ssl_cert, use_sudo=True)
                os.remove(tmp_fname)

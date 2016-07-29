import os
from time import sleep

from fabric.contrib.files import exists

from fabfile.config import *
from fabfile.utils.host import (get_keystone_certfile, get_keystone_keyfile,
                                get_keystone_cafile, get_apiserver_certfile,
                                get_apiserver_keyfile, get_apiserver_cafile,
                                get_env_passwords, get_openstack_internal_vip,
                                get_contrail_internal_vip, hstr_to_ip)
from fabfile.utils.fabos import get_as_sudo


@task
@EXECUTE_TASK
@roles('openstack')
def setup_keystone_ssl_certs():
    execute('setup_keystone_ssl_certs_node', env.host_string)


@task
def setup_keystone_ssl_certs_node(*nodes):
    default_certfile = '/etc/keystone/ssl/certs/keystone.pem'
    default_keyfile = '/etc/keystone/ssl/private/keystone_key.pem'
    default_cafile = '/etc/keystone/ssl/certs/keystone_ca.pem'
    ssl_certs = ((get_keystone_certfile(), default_certfile),
                 (get_keystone_keyfile(), default_keyfile),
                 (get_keystone_cafile(), default_cafile))
    index = env.roledefs['openstack'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    openstack_host = env.roledefs['openstack'][0]
                    if index == 1:
                        print "Creating keystone SSL certs in first openstack node"
                        sudo('create-keystone-ssl-certs.sh %s' % (
                                get_openstack_internal_vip() or hstr_to_ip(openstack_host)))
                    else:
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


@task
def setup_apiserver_ssl_certs_node(*nodes):
    default_certfile = '/etc/contrail/ssl/certs/contrail.pem'
    default_keyfile = '/etc/contrail/ssl/private/contrail.key'
    default_cafile = '/etc/contrail/ssl/certs/contrail_ca.pem'
    ssl_certs = ((get_apiserver_certfile(), default_certfile),
                 (get_apiserver_keyfile(), default_keyfile),
                 (get_apiserver_cafile(), default_cafile))
    index = env.roledefs['cfgm'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    cfgm_host = env.roledefs['cfgm'][0]
                    if index == 1:
                        print "Creating apiserver SSL certs in first cfgm node"
                        cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(cfgm_host)
                        sudo('create-api-ssl-certs.sh %s' % cfgm_ip)
                    else:
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
                    raise RuntimeError("%s doesn't exists locally or in cfgm node" % ssl_cert)


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
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert in ssl_certs:
                with settings(host_string=openstack_host,
                              password=get_env_passwords(openstack_host)):
                    tmp_fname = os.path.join('/tmp', os.path.basename(ssl_cert))
                    get_as_sudo(ssl_cert, tmp_fname)
                sudo("mkdir -p /etc/keystone/ssl/certs/")
                sudo("mkdir -p /etc/keystone/ssl/private/")
                put(tmp_fname, ssl_cert, use_sudo=True)
                os.remove(tmp_fname)

import os
import tempfile
from time import sleep

from fabric.contrib.files import exists

from fabfile.config import *
from fabfile.utils.host import (
        get_keystone_certfile, get_keystone_keyfile,
        get_keystone_cafile, get_apiserver_certfile,
        get_apiserver_keyfile, get_apiserver_cafile,
        get_env_passwords, get_openstack_internal_vip,
        get_contrail_internal_vip, hstr_to_ip,
        get_apiserver_cert_bundle, get_control_host_string,
        get_keystone_cert_bundle, get_openstack_external_vip,
        get_contrail_external_vip
        )
from fabfile.utils.fabos import get_as_sudo, get_openstack_services


@task
@EXECUTE_TASK
@roles('openstack')
def setup_keystone_ssl_certs():
    execute('setup_keystone_ssl_certs_node', env.host_string)


@task
def setup_keystone_ssl_certs_node(*nodes):
    default_certfile = '/etc/keystone/ssl/certs/keystone.pem'
    default_keyfile = '/etc/keystone/ssl/private/keystone.key'
    default_cafile = '/etc/keystone/ssl/certs/keystone_ca.pem'
    keystonecertbundle = get_keystone_cert_bundle()
    ssl_certs = ((get_keystone_certfile(), default_certfile),
                 (get_keystone_keyfile(), default_keyfile),
                 (get_keystone_cafile(), default_cafile))
    index = env.roledefs['openstack'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    # Clear old certificate
                    sudo('rm -f %s' % ssl_cert)
                    sudo('rm -f %s' % keystonecertbundle)
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    openstack_host = env.roledefs['openstack'][0]
                    if index == 1:
                        if not exists(ssl_cert, use_sudo=True):
                            print "Creating keystone SSL certs in first openstack node"
                            subject_alt_names_mgmt = [hstr_to_ip(host)
                                                      for host in env.roledefs['openstack']]
                            subject_alt_names_ctrl = [hstr_to_ip(get_control_host_string(host))
                                                      for host in env.roledefs['openstack']]
                            subject_alt_names = subject_alt_names_mgmt + subject_alt_names_ctrl
                            if get_openstack_external_vip():
                                subject_alt_names.append(get_openstack_external_vip())
                            sudo('create-keystone-ssl-certs.sh %s %s' % (
                                    get_openstack_internal_vip() or
                                    hstr_to_ip(get_control_host_string(openstack_host)),
                                    ','.join(subject_alt_names)))
                    else:
                        with settings(host_string=openstack_host,
                                      password=get_env_passwords(openstack_host)):
                            while not exists(ssl_cert, use_sudo=True):
                                print "Wait for SSL certs to be created in first openstack"
                                sleep(0.1)
                            print "Get SSL cert(%s) from first openstack" % ssl_cert
                            tmp_dir= tempfile.mkdtemp()
                            tmp_fname = os.path.join(tmp_dir, os.path.basename(ssl_cert))
                            get_as_sudo(ssl_cert, tmp_fname)
                        print "Copy to this(%s) openstack node" % env.host_string 
                        sudo('mkdir -p /etc/keystone/ssl/certs/')
                        sudo('mkdir -p /etc/keystone/ssl/private/')
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
            if not exists(keystonecertbundle, use_sudo=True):
                ((certfile, _), (keyfile, _), (cafile, _)) = ssl_certs
                sudo('cat %s %s > %s' % (certfile, cafile, keystonecertbundle))
            sudo("chown -R keystone:keystone /etc/keystone/ssl")


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
    contrailcertbundle = get_apiserver_cert_bundle()
    ssl_certs = ((get_apiserver_certfile(), default_certfile),
                 (get_apiserver_keyfile(), default_keyfile),
                 (get_apiserver_cafile(), default_cafile))
    index = env.roledefs['cfgm'].index(env.host_string) + 1
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    # Clear old certificate
                    sudo('rm -f %s' % ssl_cert)
                    sudo('rm -f %s' % contrailcertbundle)
            for ssl_cert, default in ssl_certs:
                if ssl_cert == default:
                    cfgm_host = env.roledefs['cfgm'][0]
                    if index == 1:
                        if not exists(ssl_cert, use_sudo=True):
                            print "Creating apiserver SSL certs in first cfgm node"
                            subject_alt_names_mgmt = [hstr_to_ip(host)
                                                      for host in env.roledefs['cfgm']]
                            subject_alt_names_ctrl = [hstr_to_ip(get_control_host_string(host))
                                                      for host in env.roledefs['cfgm']]
                            subject_alt_names = subject_alt_names_mgmt + subject_alt_names_ctrl
                            if get_contrail_external_vip():
                                subject_alt_names.append(get_contrail_external_vip())
                            cfgm_ip = get_contrail_internal_vip() or hstr_to_ip(get_control_host_string(cfgm_host))
                            sudo('create-api-ssl-certs.sh %s %s' % (cfgm_ip, ','.join(subject_alt_names)))
                    else:
                        with settings(host_string=cfgm_host,
                                      password=get_env_passwords(cfgm_host)):
                            while not exists(ssl_cert, use_sudo=True):
                                print "Wait for SSL certs to be created in first cfgm"
                                sleep(0.1)
                            print "Get SSL cert(%s) from first cfgm" % ssl_cert
                            tmp_dir= tempfile.mkdtemp()
                            tmp_fname = os.path.join(tmp_dir, os.path.basename(ssl_cert))
                            get_as_sudo(ssl_cert, tmp_fname)
                        print "Copy to this(%s) cfgm node" % env.host_string 
                        sudo('mkdir -p /etc/contrail/ssl/certs/')
                        sudo('mkdir -p /etc/contrail/ssl/private/')
                        put(tmp_fname, ssl_cert, use_sudo=True)
                        os.remove(tmp_fname)
                elif os.path.isfile(ssl_cert): 
                    print "Certificate (%s) exists locally" % ssl_cert
                    put(ssl_cert, default, use_sudo=True)
                elif exists(ssl_cert, use_sudo=True): 
                    print "Certificate (%s) exists in cfgm node" % ssl_cert
                else:
                    raise RuntimeError("%s doesn't exists locally or in cfgm node" % ssl_cert)
            if not exists(contrailcertbundle, use_sudo=True):
                ((certfile, _), (keyfile, _), (cafile, _)) = ssl_certs
                sudo('cat %s %s > %s' % (certfile, cafile, contrailcertbundle))
            sudo("chown -R contrail:contrail /etc/contrail/ssl")


@task
@EXECUTE_TASK
@roles('cfgm')
def copy_keystone_ssl_certs_to_config():
    execute('copy_keystone_ssl_certs_to_node', env.host_string)


@task
@EXECUTE_TASK
@roles('collector')
def copy_keystone_ssl_certs_to_collector():
    execute('copy_keystone_ssl_certs_to_node', env.host_string)


@task
@EXECUTE_TASK
@roles('compute')
def copy_keystone_ssl_certs_to_compute():
    execute('copy_keystone_ssl_certs_to_node', env.host_string)


@task
@EXECUTE_TASK
@roles('cfgm')
def use_keystone_ssl_certs_in_config():
    execute('use_keystone_ssl_certs_in_node', env.host_string)

@task
def use_keystone_ssl_certs_in_node(*nodes):
    for node in nodes:
        execute('copy_keystone_ssl_certs_to_node', node)
        execute('copy_keystone_ssl_key_to_node', node)
        with settings(host_string=node, password=get_env_passwords(node)):
            cert_path = '/etc/contrail/ssl/certs/'
            ssl_certs = (get_keystone_certfile(),
                         get_keystone_cafile())
            for ssl_cert in ssl_certs:
                src = os.path.join(cert_path, os.path.basename(ssl_cert))
                dst = os.path.join(cert_path, os.path.basename(ssl_cert).replace('keystone', 'contrail'))
                sudo("cp %s %s" % (src, dst))

            key_path = '/etc/contrail/ssl/private/'
            ssl_key = get_keystone_keyfile()
            src_key = os.path.join(key_path, os.path.basename(ssl_key))
            dst_key = os.path.join(key_path, os.path.basename(ssl_key).replace('keystone', 'contrail'))
            sudo("cp %s %s" % (src_key, dst_key))

            certfile = '/etc/contrail/ssl/certs/contrail.pem'
            cafile = '/etc/contrail/ssl/certs/contrail_ca.pem'
            contrailcertbundle = get_apiserver_cert_bundle()
            sudo('cat %s %s > %s' % (certfile, cafile, contrailcertbundle))
            sudo("chown -R contrail:contrail /etc/contrail/ssl")


@task
def copy_keystone_ssl_certs_to_node(*nodes):
    ssl_certs = (get_keystone_certfile(),
                 get_keystone_cafile())
    openstack_host = env.roledefs['openstack'][0]
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert in ssl_certs:
                cert_file = '/etc/contrail/ssl/certs/%s' % os.path.basename(ssl_cert)
                # Clear old certificate
                sudo('rm -f %s' % cert_file)
                with settings(host_string=openstack_host,
                              password=get_env_passwords(openstack_host)):
                    tmp_dir= tempfile.mkdtemp()
                    tmp_fname = os.path.join(tmp_dir, os.path.basename(ssl_cert))
                    get_as_sudo(ssl_cert, tmp_fname)
                sudo("mkdir -p /etc/contrail/ssl/certs/")
                put(tmp_fname, cert_file, use_sudo=True)
                os.remove(tmp_fname)
                with settings(warn_only=True):
                    sudo("chown -R contrail:contrail /etc/contrail/ssl")


@task
def copy_keystone_ssl_key_to_node(*nodes):
    ssl_key = get_keystone_keyfile()
    openstack_host = env.roledefs['openstack'][0]
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            key_file = '/etc/contrail/ssl/private/%s' % os.path.basename(ssl_key)
            # Clear old key
            sudo('rm -f %s' % key_file)
            with settings(host_string=openstack_host,
                          password=get_env_passwords(openstack_host)):
                tmp_dir= tempfile.mkdtemp()
                tmp_fname = os.path.join(tmp_dir, os.path.basename(ssl_key))
                get_as_sudo(ssl_key, tmp_fname)
            sudo("mkdir -p /etc/contrail/ssl/private/")
            put(tmp_fname, key_file, use_sudo=True)
            os.remove(tmp_fname)
            sudo("chown -R contrail:contrail /etc/contrail/ssl/private")


@task
@EXECUTE_TASK
@roles('config')
def copy_certs_for_neutron():
    execute('copy_certs_for_neutron_node', env.host_string)

@task
def copy_certs_for_neutron_node(*nodes):
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            sudo("mkdir -p /etc/neutron/ssl/certs/")
            sudo("cp /etc/contrail/ssl/certs/* /etc/neutron/ssl/certs/")
            sudo("chown -R neutron:neutron /etc/neutron/ssl")
            sudo("usermod -a -G contrail neutron")


@task
@EXECUTE_TASK
@roles('openstack')
def copy_certs_for_heat():
    execute('copy_certs_for_heat_node', env.host_string)

@task
def copy_certs_for_heat_node(*nodes):
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            if node in env.roledefs['cfgm']:
                sudo("usermod -a -G contrail heat")
            else:
                execute('copy_apiserver_ssl_certs_to_node', node)
                execute('copy_keystone_ssl_certs_to_node', node)
                execute('copy_vnc_api_lib_ini_to_node', node)
                sudo("chown -R heat:heat /etc/contrail")
            for svc_key in ['heat-api', 'heat-engine', 'heat-api-cfn']:
                sudo("service %s restart" % get_openstack_services()[svc_key])


@task
@EXECUTE_TASK
@roles('collector')
def copy_apiserver_ssl_certs_to_collector():
    execute('copy_apiserver_ssl_certs_to_node', env.host_string)


@task
@EXECUTE_TASK
@roles('compute')
def copy_apiserver_ssl_certs_to_compute():
    execute('copy_apiserver_ssl_certs_to_node', env.host_string)


@task
def copy_apiserver_ssl_certs_to_node(*nodes):
    ssl_certs = (get_apiserver_certfile(),
                 get_apiserver_cafile(),
                 get_apiserver_keyfile(),
                 get_apiserver_cert_bundle())
    cfgm_host = env.roledefs['cfgm'][0]
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            for ssl_cert in ssl_certs:
                cert_file = '/etc/contrail/ssl/certs/%s' % os.path.basename(ssl_cert)
                if ssl_cert.endswith('.key'):
                    cert_file = '/etc/contrail/ssl/private/%s' % os.path.basename(ssl_cert)
                if node not in env.roledefs['cfgm']:
                    # Clear old certificate
                    sudo('rm -f %s' % cert_file)
                if exists(cert_file, use_sudo=True):
                    continue
                with settings(host_string=cfgm_host,
                              password=get_env_passwords(cfgm_host)):
                    tmp_dir= tempfile.mkdtemp()
                    tmp_fname = os.path.join(tmp_dir, os.path.basename(ssl_cert))
                    get_as_sudo(ssl_cert, tmp_fname)
                sudo("mkdir -p /etc/contrail/ssl/certs/")
                sudo("mkdir -p /etc/contrail/ssl/private/")
                put(tmp_fname, cert_file, use_sudo=True)
                os.remove(tmp_fname)
                with settings(warn_only=True):
                   sudo("chown -R contrail:contrail /etc/contrail/ssl")

@task
@EXECUTE_TASK
@roles('compute')
def copy_vnc_api_lib_ini_to_compute():
    execute('copy_vnc_api_lib_ini_to_node', env.host_string)


@task
def copy_vnc_api_lib_ini_to_node(*nodes):
    vnc_api_lib = '/etc/contrail/vnc_api_lib.ini'
    cfgm_host = env.roledefs['cfgm'][0]
    for node in nodes:
        with settings(host_string=node, password=get_env_passwords(node)):
            with settings(host_string=cfgm_host,
                          password=get_env_passwords(cfgm_host)):
                tmp_dir= tempfile.mkdtemp()
                tmp_fname = os.path.join(tmp_dir, os.path.basename(vnc_api_lib))
                get_as_sudo(vnc_api_lib, tmp_fname)
            put(tmp_fname, vnc_api_lib, use_sudo=True)

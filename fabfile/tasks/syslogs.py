from datetime import datetime as dt

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype, get_container_name,\
        get_linux_distro, run_in_container, get_contrail_containers
from fabfile.utils.host import get_env_passwords, get_authserver_credentials
from fabric.contrib.files import exists
from fabfile.utils.cluster import get_orchestrator

def save_openstack_container_logs():
    # If kolla containers are present
    cmd = 'docker ps 2>/dev/null |grep kolla | awk \'{print $NF}\''
    output = sudo(cmd)
    if not output:
        return
    containers = output.split('\n')
    kolla_folder = '/var/log/kolla_logs'
    sudo('rm -rf %s' %(kolla_folder))

    for container in containers:
        container_folder = '%s/%s' %(kolla_folder, container)
        sudo('mkdir -p %s' %(container_folder))
        sudo('docker cp %s:/var/log/kolla %s' %(container, container_folder))
# end save_openstack_container_logs

def save_contrail_systemd_logs():
    containers = get_contrail_containers()
    for container in containers:
        cmd = 'journalctl > /var/log/contrail/journalctl_%s.log' %(container)
        run_in_container(container, cmd, as_sudo=True)
# end save_contrail_systemd_logs

def save_systemd_logs():
    dist, version, extra = get_linux_distro()
    # No systemd on ubuntu 14.04
    if '14.04' in version:
        return
    sudo('journalctl > /var/log/journalctl.log')
    save_contrail_systemd_logs()
    if get_orchestrator() == 'openstack':
        save_openstack_container_logs()
# end save_systemd_logs()

def check_cores_on_host(hostname):
    core_folder = '/var/crashes'
    contrail_version_log = '/var/log/contrail_version_%s.log' %(hostname)
    run('contrail-version > %s' %(contrail_version_log))
    output = run("ls -lrt %s" % (core_folder))

    if "core" in output:
        core_list = output.split('\n')
        for corename in core_list:
            if "core" in corename:
                core = corename.split()[8]
                name = core.split('.')[1]
                binary_name_cmd = 'strings %s/%s | grep "^/usr/bin/%s" | head -1' %(
                    core_folder, core, name)
                rname = run(binary_name_cmd)
                if check_file_exists(rname):
                    name = run("basename %s" %rname)
                core_new = core.rstrip('\r')
                if not check_file_exists('/usr/bin/gdb'):
                    install_gdb()
                gdb_log = '/var/log/gdb_%s.log' %(core_new)
                sudo("gdb %s /var/crashes/%s --eval-command bt > %s "
                    "--eval-command quit" %(name, core_new, gdb_log))
        sudo("mkdir -p /var/crashes/saved")
        sudo("cp /var/crashes/core* /var/crashes/saved/")
        sudo("gzip /var/crashes/core*")
        sudo("cd /var/crashes; for i in core*.gz; do mv -f $i %s_$i; done" %(hostname) )
# end check_cores_on_host

def check_cores_on_containers(hostname):
    containers = get_contrail_containers()
    core_folder = '/var/crashes'
    cores_in_containers = { 'controller': ['contro', 'dns', 'named', 'api', 'device', 'schema', 'svc', 'webui'], 'analytics': [
        'alarm', 'analyt', 'collec', 'query', 'snmp', 'topolo'], 'analyticsdb':['databa', 'kafka'] }
    for container in containers:
        contrail_version_log = '/var/log/contrail_version_%s_%s.log' %(
            hostname, container)
        run_in_container(container, 'contrail-version > %s' %(
            contrail_version_log))
        sudo('docker cp %s:%s /var/log/' %(container, contrail_version_log))
        output = run_in_container(container, "ls -lrt %s" % (core_folder))
        if "core" in output:
            core_list = output.split('\n')
            container_processes = cores_in_containers.get(container)

            for corename in core_list:
                if "core" in corename:
                    core = corename.split()[8]
                    name = core.split('.')[1]
                    check = False
                    for process in container_processes:
                        if process in name:
                            check = True
                            break
                    if not check:
                        continue
                    binary_name_cmd = 'strings %s/%s | grep "^/usr/bin/%s" | head -1' %(
                        core_folder, core, name)
                    rname = run_in_container(container, binary_name_cmd)
                    if check_file_exists(rname, container):
                        name = run_in_container(container, "basename %s" %rname)
                    core_new = core.rstrip('\r')
                    if not check_file_exists('/usr/bin/gdb', container=container):
                        install_gdb(container)
                    gdb_log = '/var/log/gdb_%s.log' %(core_new)
                    run_in_container(container,
                        "gdb %s /var/crashes/%s --eval-command bt > %s --eval-command quit"%(name, core_new, gdb_log))
                    sudo('docker cp %s:%s /var/log/' %(container, gdb_log))
            run_in_container(container, "mkdir -p /var/crashes/saved")
            run_in_container(container, "cp /var/crashes/core* /var/crashes/saved/")
            run_in_container(container, "gzip /var/crashes/core*")
            run_in_container(container, "cd /var/crashes; for i in core*.gz; do mv -f $i %s_$i; done" %(hostname) )
            sudo('docker cp %s:/var/crashes/ /var/' %(container))
# end check_cores_on_containers

def install_gdb(container=None):
	# In openstack clusters, agent is not a container
    if env.host_string in env.roledefs['compute'] and \
            'openstack' in get_orchestrator():
        execute('install_test_repo_node', None, env.host_string)
        install_pkg(['gdb'])
    else:
        execute('install_test_repo_node', container, env.host_string)
        install_pkg(['gdb'], container)

@roles('all')
@task
def tar_logs_cores():
    sudo("rm -f /var/log/logs_*.tgz")
    sudo("rm -f /var/crashes/*gz; mkdir -p /var/crashes")
    sudo("rm -f /var/log/gdb*.log")
    sudo("rm -f /var/log/contrail*.log")
    sudo("rm -rf /var/log/temp_log")
    sudo("rm -rf /var/temp_log")
    a = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    d = env.host_string
    e=sudo('hostname')
    with settings(warn_only=True):
        save_systemd_logs()
    sudo ("mkdir -p /var/temp_log; cp -R /var/log/* /var/temp_log")
    sudo ("mv /var/temp_log /var/log/temp_log")
    sudo ("cd /var/log/temp_log/ ; tar czf /var/log/logs_%s_%s.tgz *"%(e, a))
    with settings(warn_only=True):
        check_cores_on_containers(hostname=e)
        if env.host_string in env.roledefs['compute'] and \
                get_orchestrator() == 'openstack':
            check_cores_on_host(hostname=e)
#end tar_logs_cores

def check_file_exists(filepath, container=None):
    if container:
        with settings(warn_only = True):
            output = run_in_container(container, 'ls %s' %(filepath))
            if 'No such file' in output:
                return False
            else:
                return True
    elif exists(filepath):
        return True
    return False

def install_pkg(pkgs, container=None):
    ostype = detect_ostype(container=container)
    for pkg in pkgs:
        with settings(warn_only = True):
            if ostype in ['fedora', 'centos', 'redhat', 'centoslinux']:
                cmd = "yum -y install %s" % (pkg)
            elif ostype in ['ubuntu']:
                cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes install %s" %(pkg)
            if container:
                run_in_container(container, cmd)
            else:
                sudo(cmd)


#@roles('collector','contrail-analytics')
@roles('collector')
@task
def get_cassandra_logs(duration = None):
    container = get_container_name(env.host_string, 'analytics')
    if not container:
        print 'No analytics container found in %s' %(env.host_string)
        return
    if env.roledefs.get('collector'):
        first_analytics_node = env.roledefs['collector'][0]
    elif env.roledefs.get('contrail-analytics'):
        first_analytics_node = env.roledefs['contrail-analytics'][0]

    if env.host_string != first_analytics_node:
        print 'No need to get cassandra logs on this host'
        return
    sudo("rm -f /var/log/cassandra_log_*")
    a = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    d = env.host_string
    e=sudo('hostname')
    if duration is None:
        output = run_in_container(container, cmd="cat /proc/uptime")
        uptime_seconds = float(output.split()[0])
        uptime_min=uptime_seconds/60
        uptime_min=int(uptime_min)
        uptime_min=str(uptime_min) + 'm'
        print "Container %s is up for %s. Collecting Cassandra logs for %s" %(e,uptime_min,uptime_min)
    else:
        uptime_min=str(duration) + 'm'
        print "Duration value is %s . Collecting Cassandra logs for %s" %(uptime_min,uptime_min)
    cmd = "/usr/bin/contrail-logs --last %s --all" %(uptime_min)
    admin_user, admin_password = get_authserver_credentials()
    cmd += " --admin-user %s --admin-password %s" % (admin_user, admin_password)
    cassandra_log = '/var/log/contrail/cassandra_log_%s_%s.log' %(e,a)
    with settings(warn_only=True):
        run_in_container(container, "%s -o %s" %(cmd, cassandra_log))
        run_in_container(container, "gzip %s" %(cassandra_log))
        sudo('docker cp %s:%s.gz /var/log/' %(container, cassandra_log))
        print "\nCassandra logs are saved in /var/log/cassandra_log_%s_%s.log" %(e,a)
#end get_cassandra_logs

@roles('database')
def get_cassandra_db_files():
    sudo("rm -rf /var/cassandra_log")
    a = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    d = env.host_string
    e = sudo('hostname')
    sudo("mkdir -p /var/cassandra_log")
    if exists('/home/cassandra/'):
        sudo("cp -R /home/cassandra/* /var/cassandra_log")
    elif exists('/var/lib/cassandra/'):
        sudo("cp -R /var/lib/cassandra/* /var/cassandra_log")
    else:
        print "cassandra directory not available in standard location..."
    sudo("cd /var/cassandra_log; tar -czf cassandra_file_%s_%s.tgz *" %(e,a))
    print "\nCassandra DB files are saved in /var/cassandra_log/cassandra_file_%s_%s.tgz of %s" %( e,a ,e)
#end get_cassandra_db_file

@roles('build')
@task
def attach_logs_cores(bug_id, timestamp=None, duration=None, analytics_log='yes'):
    '''
    Attach the logs, core-files, bt and contrail-version to a specified location
    
    If argument duration is specified it will collect the cassandra logs for specifed
    duration. Unit of the argument duration is minute. If not specifed it will collect
    cassandra log for system uptime
    '''
    build= env.roledefs['build'][0]
    if timestamp:
        folder= '%s/%s' %( bug_id, timestamp) 
    else:
        time_str = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        folder='%s/%s' %(bug_id, time_str)
    local('mkdir -p %s' % ( folder ) )
    execute(tar_logs_cores)
    if analytics_log == 'yes':
        execute(get_cassandra_logs,duration)
    with hide('everything'):
        for host in env.roledefs['all']:
            with settings( host_string=host, password=get_env_passwords(host),
                           connection_attempts=3, timeout=20, warn_only=True):
                get('/var/log/logs_*.tgz', '%s/' %( folder ) )
                get('/var/crashes/*gz', '%s/' %( folder ) )
                get('/var/log/gdb_*.log','%s/' %( folder ) )
                get('/var/log/contrail_version*.log','%s/' %( folder ) )
                if analytics_log is 'yes':
                    get('/var/log/cassandra_log*.gz','%s/' %( folder ) )

    print "\nAll logs and cores are saved in %s of %s" %(folder, env.host)
#end attach_logs_cores

import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import hstr_to_ip
from fabfile.tasks.upgrade import upgrade_package, remove_package

@task
@EXECUTE_TASK
@roles('cfgm')
def backup_zookeeper_database():
    backup_dir = "/opt/contrail/backup/zookeeper"
    with settings(warn_only=True):
        run("mkdir -p %s" % backup_dir)
        run("cp -r /var/lib/zookeeper/* %s" % backup_dir)

@task
def restart_zookeeper():
    restart_cmd = "/usr/lib/zookeeper/bin/zkServer.sh restart"
    if detect_ostype() in ['Ubuntu']:
        restart_cmd = "/usr/share/zookeeper/bin/zkServer.sh restart"
    with settings(warn_only=True):
        if run("service zookeeper restart").failed:
            run(restart_cmd)

@task
def stop_zookeeper():
    stop_cmd = "/usr/lib/zookeeper/bin/zkServer.sh stop"
    if detect_ostype() in ['Ubuntu']:
        stop_cmd = "/usr/share/zookeeper/bin/zkServer.sh stop"
    with settings(warn_only=True):
        if run("service zookeeper stop").failed:
            run(stop_cmd)

@task
@roles('build')
def zookeeper_rolling_restart():
    zoo_cfg = "/etc/zookeeper/conf/zoo.cfg"
    cfgm_nodes = copy.deepcopy(env.roledefs['cfgm'])
    database_nodes = copy.deepcopy(env.roledefs['database'])
    zookeeper_status = verfiy_zookeeper(*database_nodes)
    if (len(database_nodes) % 2) != 1:
        print "Recommended to run odd number of zookeeper(database) nodes."
        print "Add a new node to the existing clusters testbed,py and install contrail-install-packages in it.\n\
               Installing/Provisioning will be done as part of Upgrade"
        exit(0)

    if cfgm_nodes == database_nodes:
        print "No need for rolling restart."

    if (len(database_nodes) > 1 and
        'leader' in zookeeper_status.values() and
        'follower' in zookeeper_status.values() and
        'notrunning' not in zookeeper_status.values() and
        'notinstalled' not in zookeeper_status.values() and
        'standalone' not in zookeeper_status.values()):
        print zookeeper_status
        print "Zookeeper quorum is already formed properly."
        return
    elif (len(database_nodes) == 1 and
        'notinstalled' not in zookeeper_status.values() and
        'standalone' in zookeeper_status.values()):
        print zookeeper_status
        print "Zookeeper quorum is already formed properly."
        return

    execute('stop_cfgm')
    execute('backup_zookeeper_database')

    old_nodes = list(set(cfgm_nodes).difference(set(database_nodes)))
    new_nodes = list(set(database_nodes).difference(set(cfgm_nodes)))

    for new_node in new_nodes:
        zk_index = (database_nodes.index(new_node) + len(cfgm_nodes) + 1)
        with settings(host_string=new_node, password=env.passwords[new_node]):
            pdist = detect_ostype()
            print "Install zookeeper in the new node."
            execute('create_install_repo_node', new_node)
            remove_package(['supervisor'], pdist)
            upgrade_package(['python-contrail', 'contrail-openstack-database', 'zookeeper'], pdist)
            if pdist in ['Ubuntu']:
                run("ln -sf /bin/true /sbin/chkconfig")
            run("chkconfig zookeeper on")
            print "Fix zookeeper configs"
            run("sudo sed 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=/log4j.appender.ROLLINGFILE.MaxBackupIndex=/g' /etc/zookeeper/conf/log4j.properties > log4j.properties.new")
            run("sudo mv log4j.properties.new /etc/zookeeper/conf/log4j.properties")
            if pdist in ['centos']:
                run('echo export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /usr/lib/zookeeper/bin/zkEnv.sh')
            if pdist in ['Ubuntu']:
                run('echo ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /etc/zookeeper/conf/environment')
            print "put cluster-unique zookeeper's instance id in myid"
            run('sudo echo "%s" > /var/lib/zookeeper/myid' % (zk_index))

    print "Add new nodes to existing zookeeper quorum"
    with settings(host_string=cfgm_nodes[0], password=env.passwords[cfgm_nodes[0]]):
        for new_node in new_nodes:
            zk_index = (database_nodes.index(new_node) + len(cfgm_nodes) + 1)
            run('echo "server.%d=%s:2888:3888" >> %s' % (zk_index, hstr_to_ip(new_node), zoo_cfg))
        tmp_dir= tempfile.mkdtemp()
        get(zoo_cfg, tmp_dir)

    print "Restart zookeeper in all nodes to make new nodes join zookeeper quorum"
    for zookeeper_node in cfgm_nodes + new_nodes:
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            put(tmp_dir+'/zoo.cfg', zoo_cfg)
            print "Start Zookeeper in new database node"
            execute('restart_zookeeper')

    print "Waiting 5 seconds for the new nodes in the zookeeper quorum to be synced."
    sleep(5)
    print "Shutdown old nodes one by one and also make sure leader/follower election is complete after each shut downs"
    zoo_nodes = cfgm_nodes + database_nodes
    for old_node in old_nodes:
        zoo_nodes.remove(old_node)
        with settings(host_string=old_node, password=env.passwords[old_node]):
            print "Stop Zookeeper in old cfgm node"
            execute('stop_zookeeper')
            for zoo_node in zoo_nodes:
                with settings(host_string=zoo_node, password=env.passwords[zoo_node]):
                    run("sed -i '/^server.*%s:2888:3888/d' %s" % (hstr_to_ip(zoo_node), zoo_cfg))
            retries = 3
            while retries:
                zookeeper_status = verfiy_zookeeper(*zoo_nodes)
                if (len(zoo_nodes) > 1 and
                    'leader' in zookeeper_status.values() and
                    'follower' in zookeeper_status.values() and
                    'notrunning' not in zookeeper_status.values() and
                    'notinstalled' not in zookeeper_status.values() and
                    'standalone' not in zookeeper_status.values()):
                    print zookeeper_status
                    print "Zookeeper quorum is formed properly."
                    break
                elif (len(zoo_nodes) == 1 and
                    'notinstalled' not in zookeeper_status.values() and
                    'standalone' in zookeeper_status.values()):
                    print zookeeper_status
                    print "Zookeeper quorum is formed properly."
                    break
                else:
                    retries -= 1
                    if retries:
                        for zoo_node in zoo_nodes:
                            with settings(host_string=zoo_node, password=env.passwords[zoo_node]):
                                execute('restart_zookeeper')
                        continue
                    print "Zookeeper quorum is not formed. Fix it and retry upgrade"
                    print zookeeper_status
                    exit(1)
          
    print "Correct the server id in zoo.cfg for the new nodes in the zookeeper quorum"
    with settings(host_string=database_nodes[0], password=env.passwords[database_nodes[0]]):
        run("sed -i '/^server.*3888/d' %s" % zoo_cfg)
        for zookeeper_node in database_nodes:
            zk_index = (database_nodes.index(zookeeper_node) + 1)
            run('echo "server.%d=%s:2888:3888" >> %s' % (zk_index, hstr_to_ip(zookeeper_node), zoo_cfg))
        tmp_dir= tempfile.mkdtemp()
        get(zoo_cfg, tmp_dir)

    print "Correct the myid in myid file for the new nodes in the zookeeper quorum"
    for zookeeper_node in database_nodes:
        zk_index = (database_nodes.index(zookeeper_node) + 1)
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            print "put cluster-unique zookeeper's instance id in myid"
            run('sudo echo "%s" > /var/lib/zookeeper/myid' % (zk_index))
            execute('stop_zookeeper')

    print "Restart all the zookeeper nodes in the new quorum"
    for zookeeper_node in database_nodes:
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            put(tmp_dir+'/zoo.cfg', zoo_cfg)
            execute('restart_zookeeper')

    print "Make sure leader/folower election is complete"
    with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
        retries = 3
        while retries:
            zookeeper_status = verfiy_zookeeper(*database_nodes)
            if (len(database_nodes) > 1 and
                'leader' in zookeeper_status.values() and
                'follower' in zookeeper_status.values() and
                'notrunning' not in zookeeper_status.values() and
                'notinstalled' not in zookeeper_status.values() and
                'standalone' not in zookeeper_status.values()):
                print zookeeper_status
                break
            elif (len(database_nodes) == 1 and
                'notinstalled' not in zookeeper_status.values() and
                'standalone' in zookeeper_status.values()):
                print zookeeper_status
                print "Zookeeper quorum is already formed properly."
                break
            else:
                retries -= 1
                if retries:
                    continue
                print "Zookeepr leader/follower election has problems. Fix it and retry upgrade"
                print zookeeper_status
                exit(1)


def verfiy_zookeeper(*zoo_nodes):
    zookeeper_status = {}
    for host_string in zoo_nodes:
        with settings(host_string=host_string, warn_only=True):
            status_cmd = "/usr/lib/zookeeper/bin/zkServer.sh status"
            if detect_ostype() in ['Ubuntu']:
                status_cmd = "/usr/share/zookeeper/bin/zkServer.sh status"
            retries = 5
            for i in range(retries):
                status = run(status_cmd)
                if 'not running' in status:
                    status = 'notrunning'
                elif 'No such file' in status:
                    status = 'notinstalled'
                elif 'Error contacting service' not in status:
                    break
                sleep(2)
            for stat in ['leader', 'follower', 'standalone']:
                if stat in status:
                    status = stat
                    break
            zookeeper_status.update({host_string: status})
    return zookeeper_status

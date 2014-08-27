import copy
import tempfile

from fabfile.config import *
from fabfile.utils.fabos import detect_ostype
from fabfile.utils.host import hstr_to_ip
from fabfile.tasks.upgrade import upgrade_package


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

    if 'leader' in zookeeper_status.values() and 'standalone' not in zookeeper_status.values():
        print zookeeper_status
        print "Zookeeper quorum is already formed properly."
        return

    old_nodes = list(set(cfgm_nodes).difference(set(database_nodes)))
    new_nodes = list(set(database_nodes).difference(set(cfgm_nodes)))

    for new_node in new_nodes:
        zk_index = (database_nodes.index(new_node) + len(cfgm_nodes) + 1)
        with settings(host_string=new_node, password=env.passwords[new_node]):
            pdist = detect_ostype()
            # Install zookeeper in the new node.
            execute('create_install_repo_node', new_node)
            upgrade_package(['python-contrail', 'contrail-openstack-database'], pdist)
            if pdist in ['Ubuntu']:
                run("ln -sf /bin/true /sbin/chkconfig")
            run("chkconfig zookeeper on")
            # Fix zookeeper configs
            run("sudo sed 's/^#log4j.appender.ROLLINGFILE.MaxBackupIndex=/log4j.appender.ROLLINGFILE.MaxBackupIndex=/g' /etc/zookeeper/conf/log4j.properties > log4j.properties.new")
            run("sudo mv log4j.properties.new /etc/zookeeper/conf/log4j.properties")
            if pdist in ['centos']:
                run('echo export ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /usr/lib/zookeeper/bin/zkEnv.sh')
            if pdist in ['Ubuntu']:
                run('echo ZOO_LOG4J_PROP="INFO,CONSOLE,ROLLINGFILE" >> /etc/zookeeper/conf/environment')
            #put cluster-unique zookeeper's instance id in myid
            run('sudo echo "%s" > /var/lib/zookeeper/myid' % (zk_index))

    # Add new nodes to existing zookeeper quorum
    with settings(host_string=cfgm_nodes[0], password=env.passwords[cfgm_nodes[0]]):
        for new_node in new_nodes:
            zk_index = (database_nodes.index(new_node) + len(cfgm_nodes) + 1)
            run('echo "server.%d=%s:2888:3888" >> %s' % (zk_index, hstr_to_ip(new_node), zoo_cfg))
        tmp_dir= tempfile.mkdtemp()
        get(zoo_cfg, tmp_dir)

    # Restart zookeeper in all nodes to make new nodes join zookeeper quorum
    for zookeeper_node in cfgm_nodes + new_nodes:
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            put(tmp_dir+'/zoo.cfg', zoo_cfg)
            # Start Zookeeper in new database node
            run("service zookeeper restart")

    print "Waiting 5 seconds for the new nodes in the zookeeper quorum to be synced."
    sleep(5)
    # Shutdown onld nodes one by one and also make sure leader/follower election is complete.
    # after each shut downs
    zoo_nodes = cfgm_nodes + database_nodes
    for old_node in old_nodes:
        zoo_nodes.remove(old_node)
        with settings(host_string=old_node, password=env.passwords[old_node]):
            # Stop Zookeeper in old cfgm node
            run("service zookeeper stop")
            retries = 3
            while retries:
                zookeeper_status = verfiy_zookeeper(*zoo_nodes)
                if 'leader' in zookeeper_status.values() and 'standalone' not in zookeeper_status.values():
                    print zookeeper_status
                    break
                else:
                    retries -= 1
                    if retries:
                        continue
                    print "Zookeeper quorum is not formed. Fix it and retry upgrade"
                    print zookeeper_status
                    exit(1)
          
    # Correct the server id in zoo.cfg for the new nodes in the zookeeper quorum
    with settings(host_string=database_nodes[0], password=env.passwords[database_nodes[0]]):
        run("sed -i '/^server.*3888/d' %s" % zoo_cfg)
        for zookeeper_node in database_nodes:
            zk_index = (database_nodes.index(zookeeper_node) + 1)
            run('echo "server.%d=%s:2888:3888" >> %s' % (zk_index, hstr_to_ip(zookeeper_node), zoo_cfg))
        tmp_dir= tempfile.mkdtemp()
        get(zoo_cfg, tmp_dir)

    # Correct the myid in myid file for the new nodes in the zookeeper quorum
    for zookeeper_node in database_nodes:
        zk_index = (database_nodes.index(zookeeper_node) + 1)
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            #put cluster-unique zookeeper's instance id in myid
            run('sudo echo "%s" > /var/lib/zookeeper/myid' % (zk_index))
            run("service zookeeper stop")

    # Restart all the zookeeper nodes in the new quorum
    for zookeeper_node in database_nodes:
        with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
            put(tmp_dir+'/zoo.cfg', zoo_cfg)
            run("service zookeeper restart")

    # Mkae sure leader/folower election is complete
    with settings(host_string=zookeeper_node, password=env.passwords[zookeeper_node]):
        retries = 3
        while retries:
            zookeeper_status = verfiy_zookeeper(*database_nodes)
            if 'leader' in zookeeper_status.values() and 'standalone' not in zookeeper_status.values():
                print zookeeper_status
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
    status_cmd = "/usr/share/zookeeper/bin/zkServer.sh status"
    for host_string in zoo_nodes:
        with settings(host_string=host_string, warn_only=True):
            retries = 5
            for i in range(retries):
                status = run(status_cmd)
                if 'Error contacting service' not in status:
                    break
                sleep(2)
            for stat in ['leader', 'follower', 'standalone']:
                if stat in status:
                    status = stat
                    break
            zookeeper_status.update({host_string: status})
    return zookeeper_status

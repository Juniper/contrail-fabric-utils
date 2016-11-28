import subprocess
from fabfile.config import *
from fabfile.utils.fabos import *
from fabfile.utils.host import *
from fabric.contrib.files import exists
from fabfile.utils.fabos import detect_ostype
from fabfile.tasks.services import *
from fabfile.tasks.zookeeper import *
import string
import time
import re
# Define global path for taking backup and restore
backup_path = '~/contrail_bkup_data/'

# Referance dir name for custom directories and it will use during the backup.
final_dir = ''


@task
def backup_data():
    '''
    Backup will happen for following tasks.
    1.Cassandra_db
    2.Mysql_db
    3.zookeeper data
    4.Instances_data
    '''
    try:
        execute(backup_cassandra_db)
        execute(backup_mysql_db)
        execute(backup_glance_image)
        execute(backup_zookeeper_data)
        execute(backup_nova_instance_data)

    except SystemExit:
        raise SystemExit("\nBackup of  all DB  Failed .... Aborting")

# end backup_data


@task
def restore_data():
    '''
    Restore will happen for following tasks.
    1.Cassandra_db
    2.Mysql_db
    3.zookeeper data
    4.Instances_data
    '''
    try:
        execute(restore_cassandra_db)
        execute(restore_mysql_db)
        execute(restore_glance_image)
        execute(restore_zookeeper_data)
        execute(restart_neutron_server)
        execute(restart_analytics)
        execute(restore_nova_instance_data)

    except SystemExit:
        raise SystemExit("\nRestore of  all  DB  Failed .... Aborting")

# end restore_data


@task
def backup_cassandra_db():
    '''
    Get target backup node & call main function - backup_cassandra
    Testbed.py is inspected for remote_node definition.
        Option available to define destination path in case of remote node..
    '''
    db_datas = getattr(testbed, 'backup_db_path', None)
    backup_node = getattr(testbed, 'backup_node', None)
    cassandra_backup = getattr(testbed, 'cassandra_backup', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'
    try:
        execute(backup_cassandra, db_datas, store_db, cassandra_backup)
    except SystemExit:
        raise SystemExit("\nBackup cassandra DB Failed .... Aborting")

# end backup_cassandra_db


@task
def backup_mysql_db():
    '''
    Get target backup node & call main function - backup_mysql
    Testbed.py is inspected for remote_node definition.
        Option available to define destination path in case of remote node..
    '''
    db_datas = getattr(testbed, 'backup_db_path', None)
    backup_node = getattr(testbed, 'backup_node', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'
    try:
        execute(backup_mysql, db_datas, store_db)
    except SystemExit:
        raise SystemExit("\nBackup Mysql DB Failed .... Aborting")

# end backup_mysql_db

@task
def backup_glance_image():
    '''
    Get target backup node & call main function - backup_instances
    Testbed.py is inspected for remote_node definition.
        Option available to define destination path in case of remote node..
    '''
    db_datas = getattr(testbed, 'backup_db_path', None)
    backup_node = getattr(testbed, 'backup_node', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'
    try:
        execute(backup_instance_image, db_datas, store_db)
    except SystemExit:
        raise SystemExit("\nBackup nova instance data Failed .... Aborting")

# end backup_glance_image

@task
def backup_zookeeper_data():
    '''
    Get target backup node & call main function - backup_zookeeper
    Testbed.py is inspected for remote_node definition.
        Option available to define destination path in case of remote node..
    '''
    db_datas = getattr(testbed, 'backup_db_path', None)
    backup_node = getattr(testbed, 'backup_node', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'
    try:
        execute(backup_zookeeper, db_datas, store_db)
    except SystemExit:
        raise SystemExit("\nBackup zookeeper data Failed .... Aborting")

# end backup_zookeeper_data


@task
def backup_nova_instance_data():
    '''
    Get target backup node & call main function - backup_instances
    Testbed.py is inspected for remote_node definition.
        Option available to define destination path in case of remote node..
    '''
    db_datas = getattr(testbed, 'backup_db_path', None)
    backup_node = getattr(testbed, 'backup_node', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'
    try:
        execute(backup_instances, db_datas, store_db)
    except SystemExit:
        raise SystemExit("\nBackup nova instance data Failed .... Aborting")

# end backup_nova_instance_data


@roles('database', 'cfgm')
def backup_cassandra(db_datas, store_db='local', cassandra_backup='full'):
    """Backup cassandra data in all databases  """
    global backup_path, final_dir
    snapshot_list=[]
    skip_key=None
    host = env.host_string
    skip_key = None
    msg = "Processing the Cassandra DB backup and default path for backup DB data is ~/contrail_bkup_data/hostname/data/ in ({HOST})  \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing the Cassandra DB Backup and puting DB dabckup data into remote host:({HOST}) and default path is ~/contrail_bkup_data/hostname/data/ or backup path is defined  as per testbed.py file  \n "
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        OS= sudo("cat /etc/os-release  | awk 'FNR == 1 {print $1 }'| awk  -F '\"' '{print $2}'") 
        if OS == 'Ubuntu' :
           snap_path = sudo(
                           "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/cassandra.yaml")
        if OS == 'CentOS' :
           snap_path = sudo(
                           "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/conf/cassandra.yaml") 
        snapshot_path = snap_path.split(' ')
        db_path = snapshot_path[-1]
        execute(verify_disk_space, db_datas, db_path, store_db)
        dir_name = '%s%s/' % (backup_path, host_name)
        if db_datas:
            dir_name = final_dir + '%s/' % (host_name)
        if exists('backup_info.txt'):
            sudo('rm -rf backup_info.txt')
        with cd(db_path):
            if cassandra_backup == 'custom':
                skip_key = getattr(testbed, 'skip_keyspace', None)
                if not skip_key: 
                    print "Need to Define the keyspace names in testbed.py if your are selected as custom snapshot. So that it will omit those keyspace name during the  database snapshot"
                    raise SystemExit()
                cs_key = sudo('ls')
                cs_key = cs_key.translate(string.maketrans("\n\t\r", "   "))
                custom_key = replace_key(cs_key, skip_key)
                nodetool_cmd = 'nodetool -h localhost -p 7199 snapshot %s ' % custom_key
                skip_key = ','.join(skip_key)
            else:
                nodetool_cmd = 'nodetool -h localhost -p 7199 snapshot'
        sudo(nodetool_cmd)
        #skip snapshots of skipped_keyspaces if already present
        if skip_key:
            snapshot_dirs = sudo("find %s/  -name 'snapshots' | egrep -v $(echo %s | sed -r 's/,/|/g')" %(db_path,skip_key))
        else:
            snapshot_dirs = sudo("find %s/  -name 'snapshots' " % db_path)
        snapshot_dirs = snapshot_dirs.split('\r\n')
        #get relative path to cassandra from db_path 
        path_to_cassandra, data_dir = os.path.split(db_path)
        while data_dir == '':
            path_to_cassandra, data_dir = os.path.split(path_to_cassandra)
        path_to_cassandra += '/'
        for snapshot_dir in snapshot_dirs:
            snapshot_list.append(snapshot_dir.replace(path_to_cassandra,''))
        #get current snap_shot name from any snapshots folder created by nodetool
        snapshot_list_name = snapshot_dirs[0]
        with cd(snapshot_list_name):
            snapshot_name = sudo('ls -t | head -n1')
        print "Cassandra DB Snapshot Name: %s" % (snapshot_name)
        if store_db == 'local':
            with cd(path_to_cassandra):
                for snapshot in snapshot_list:
                    sudo('cp --parents -R %s/%s  %s ' % (snapshot,snapshot_name,dir_name))      
        execute(backup_info_file, dir_name, backup_type='Cassandra')
        if store_db == 'local':
            sudo('cp backup_info.txt %s' % dir_name)
        if store_db == 'remote':
            execute(ssh_key_gen)
            with cd(path_to_cassandra):
                for snapshot in snapshot_list:
                    remote_path = '%s' % (dir_name)
                    if not exists(os.path.join(path_to_cassandra,snapshot, snapshot_name)):
                        continue
                    remote_cmd = 'rsync -avzR -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" %s/%s %s:%s' %(snapshot,snapshot_name,remote_host,remote_path)
                    sudo(remote_cmd)
                    
# end backup_cassandra


@roles('openstack')
def backup_mysql(db_datas, store_db='local'):
    """Backup mysql data to all opentstack databases and usuage is fab backup_mysql_db """
    host = env.host_string
    global backup_path, final_dir
    msg = "Processing Mysql DB backup and default path for backup data is ~/contrail_bkup_data/hostname/openstack.sql in ({HOST}) \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing MysqlDB Backup and keeping mysql DB backup data into remote host:({HOST})and default path is ~/contrail_bkup_data/hostname/openstack.sql or backup path is defined as per testbed.py file \n"
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        db_path = '$PWD'
        execute(verify_disk_space, db_datas, db_path, store_db)
        remote_dir_name = '%s%s/' % (backup_path, host_name)
        if db_datas:
            remote_dir_name = final_dir + '%s/' % (host_name)
    with settings(host_string=host):
        mysql_passwd = sudo('cat /etc/contrail/mysql.token')
        if exists('openstack.sql') :
            sudo('rm -r openstack.sql')
        mysql_cmd = 'mysqldump -u root --password=%s --all-databases --skip-add-locks --ignore-table=mysql.event > openstack.sql' %(
            mysql_passwd)
        sudo(mysql_cmd)
        if store_db == 'local':
            sudo('cp openstack.sql  %s ' % remote_dir_name)
        execute(backup_info_file, remote_dir_name, backup_type='Mysql')
        if store_db == 'local':
            sudo('cp backup_info.txt  %s' % remote_dir_name)
        if store_db == 'remote':
            remote_path = '%s ' % (remote_dir_name)
            source_path = 'openstack.sql  backup_info.txt'
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r   %s  %s:%s' % (
                         source_path,
                remote_host,
                remote_path)
            sudo(remote_cmd)
        sudo('rm -rf openstack.sql')
# end backup_mysql

@roles('openstack')
def backup_instance_image(db_datas, store_db='local'):
    """Backup glance images  to all openstack nodes """
    host = env.host_string
    global backup_path, final_dir
    msg = "Processing glance images backup and default path for backup data is ~/contrail_bkup_data/hostname/images  in ({HOST}) \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing glance image Backup and puting glance image backup  into remote host:({HOST}) and default path is ~/contrail_bkup_data/hostname/images or backup path is defined as per testbed.py file \n"
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        images_path = sudo("grep  'filesystem_store_datadir'   /etc/glance/glance-api.conf | grep -v '#' ")
        images_path = images_path.split('=')
        images_path = images_path[-1]
        images_path=images_path.strip() 
        images_path=images_path.split('glance')
        images_path=images_path[0] 
        db_path = images_path
        execute(verify_disk_space, db_datas, db_path, store_db)
        remote_image_path = '%s%s/' % (backup_path, host_name)
        if db_datas:
            remote_image_path = final_dir + '%s/' % (host_name)
        if store_db == 'local':
            sudo(
                ' rsync -az --progress  %sglance  %s ' %
                (images_path, remote_image_path))
        execute(
            backup_info_file,
            remote_image_path,
            backup_type='Nova-boot-images')
        if store_db == 'local':
            sudo('cp backup_info.txt %s' % remote_image_path)
        if store_db == 'remote':
            remote_path = '%s' % (remote_image_path)
            source_path = '%sglance  ' % (images_path)
            execute(ssh_key_gen)
            remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress    %s   %s:%s' %(  source_path,remote_host,remote_path)
            sudo(remote_cmd)   
            remote_bk_cmd = 'scp -o "StrictHostKeyChecking no" -r  backup_info.txt  %s:%s' % (
                remote_host,
                remote_path)
            sudo(remote_bk_cmd)
# end backup_instances_images

@roles('database', 'cfgm')
def backup_zookeeper(db_datas, store_db='local'):
    """Backup zookeeper data to all database nodes """
    host = env.host_string
    global backup_path, final_dir
    msg = "Processing zookeeper backup and default path for backup data is ~/contrail_bkup_data/hostname/zookeeper  in ({HOST}) \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing zookeeper data Backup into remote host:({HOST}) and default path is ~/contrail_bkup_data/hostname/zookeeper or backup path is defined as per testbed.py file \n"
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        data_path = sudo("grep  'dataDir'   /etc/zookeeper/conf/zoo.cfg")
        zoo_path = data_path.split('=')
        zoo_path = zoo_path[-1]
        zoo_path = zoo_path.strip() 
        db_path = zoo_path
        execute(verify_disk_space, db_datas, db_path, store_db)
        remote_image_path = '%s%s/' % (backup_path, host_name)
        if db_datas:
            remote_image_path = final_dir + '%s/' % (host_name)
        if store_db == 'local':
            sudo(
                ' rsync -az --progress  %s  %s ' %
                (zoo_path, remote_image_path))
        execute(
            backup_info_file,
            remote_image_path,
            backup_type='zookeeper data')
        if store_db == 'local':
            sudo('cp backup_info.txt %s' % remote_image_path)
        if store_db == 'remote':
            remote_path = '%s' % (remote_image_path)
            source_path = '%s  ' % (zoo_path)
            execute(ssh_key_gen)
            remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress    %s   %s:%s' %(  source_path,remote_host,remote_path)
            sudo(remote_cmd)   
            remote_bk_cmd = 'scp -o "StrictHostKeyChecking no" -r  backup_info.txt  %s:%s' % (
                remote_host,
                remote_path)
            sudo(remote_bk_cmd)
# end backup_zookeeper


@roles('compute')
def backup_instances(db_datas, store_db='local'):
    """Backup instances data to all compute nodes """
    host = env.host_string
    global backup_path, final_dir
    tsn_nodes = []
    tor_nodes = []
    msg = "Processing instances backup and default path for backup data is ~/contrail_bkup_data/hostname/instances  in ({HOST}) \n"
    if 'tsn' in env.roledefs:
        tsn_nodes = env.roledefs['tsn']
    if 'toragent' in env.roledefs:
        tor_nodes = env.roledefs['toragent']
    if host not in (tsn_nodes and tor_nodes) :
        with settings(host_string=host):
            host_name = sudo('hostname')
            if store_db == 'local':
                print (msg.format(HOST=host_name))
            if store_db == 'remote':
                msg = "Processing instances data Backup and puting instances backup data into remote host:({HOST}) and default path is ~/contrail_bkup_data/hostname/instances or backup path is defined as per testbed.py file \n"
                remote_host = env.roledefs['backup'][0]
                print (msg.format(HOST=remote_host))
            insta_path = sudo("grep  '^state_path'   /etc/nova/nova.conf")
            instances_path = insta_path.split('=')
            instances_path = instances_path[-1]
            instances_path = instances_path.strip()
            db_path = instances_path
            execute(verify_disk_space, db_datas, db_path, store_db)
            remote_instances_path = '%s%s/' % (backup_path, host_name)
            if db_datas:
                remote_instances_path = final_dir + '%s/' % (host_name)
            if store_db == 'local':
               sudo(
                    'rsync -az --progress   %s/instances    %s' %
                    (instances_path, remote_instances_path))
            execute(
                backup_info_file,
                remote_instances_path,
                backup_type='Instances')
            if store_db == 'local':
                sudo('cp backup_info.txt %s' % remote_instances_path)
            if store_db == 'remote':
                remote_path = '%s' % (remote_instances_path)
                source_path = '%s/instances' % (instances_path)
                execute(ssh_key_gen)
                remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress    %s   %s:%s' %(  source_path,remote_host,remote_path)
                sudo(remote_cmd)
                remote_bk_cmd = 'scp -o "StrictHostKeyChecking no" -r  backup_info.txt  %s:%s' % (
                    remote_host,
                    remote_path)
                sudo(remote_bk_cmd)
            sudo('rm -rf backup_info.txt')
# end backup_instances

def verify_disk_space(db_datas, db_path, store_db):
    host = env.host_string
    global backup_path, final_dir
    final_bk_dir = []
    with settings(host_string=host):
        host_name = sudo('hostname')
        with cd(db_path):
            usage_dk_space = sudo("du -ck  $PWD | grep 'total'")
            make_avail = sudo("du -ckh  $PWD | grep 'total'")
            usage_dk_space = usage_dk_space.split('\t')
            usage_dk_space = int(usage_dk_space[0])
            used_dk_space = usage_dk_space * 1.2
        if store_db == 'local':
            if not db_datas:
                with settings(warn_only=True):
                    sudo('mkdir %s' % backup_path)
                    sudo('mkdir %s%s' % (backup_path, host_name))
                with cd('%s%s' % (backup_path, host_name)):
                    free_dk_space = sudo(
                        "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                    free_dk_space = int(free_dk_space)
            if db_datas:
                for get_dir in db_datas:
                    with cd('%s' % get_dir):
                        free_dk_space = sudo(
                            "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                        free_dk_space = int(free_dk_space)
                        if free_dk_space >= used_dk_space:
                            final_bk_dir.append(get_dir)
                with settings(warn_only=True):
                    sudo('mkdir %s%s/ ' % (final_bk_dir[0], host_name))
                final_dir = final_bk_dir[0]
    if store_db == 'remote':
        remote_host = env.roledefs['backup'][0]
        with settings(host_string=env.roledefs['backup'][0]):
            if not db_datas:
                with settings(warn_only=True):
                    sudo('mkdir %s' % backup_path)
                    sudo('mkdir %s%s' % (backup_path, host_name))
                with cd('%s%s' % (backup_path, host_name)):
                    free_dk_space = sudo(
                        "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                    free_dk_space = int(free_dk_space)
            if db_datas:
                for get_dir in db_datas:
                    with cd('%s' % get_dir):
                        free_dk_space = sudo(
                            "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                        free_dk_space = int(free_dk_space)
                        if free_dk_space >= used_dk_space:
                            final_bk_dir.append(get_dir)
                with settings(warn_only=True):
                    sudo('mkdir %s%s/ ' % (final_bk_dir[0], host_name))
                final_dir = final_bk_dir[0]
    if db_datas:
        if final_bk_dir == []:
            print "Cannot  proceed for backup since disk space is not sufficent. Please make the disk space:%s available  for taking the backup" % make_avail
            raise SystemExit()
    if not db_datas:
        if used_dk_space > free_dk_space:
            print "Cannot  proceed for backup since disk space is not sufficent. Please make the disk space:%s available  for taking the backup" % make_avail
            raise SystemExit()
# end verify_disk_space


def backup_info_file(path, backup_type=''):
    host = env.host_string
    with settings(host_string=host):
        cassandra_backup = getattr(testbed, 'cassandra_backup', None)
        ubuntu_os = sudo(
            "cat /etc/lsb-release | awk 'FNR == 1 {print}' | cut -d '=' -f2")
        cent_os = sudo("cat /etc/system-release |  awk  '{print $1 $2}'")
        release_ver = sudo(
            "contrail-version | grep 'contrail-install-packages' | awk  '{print $2}'")
        sudo("echo '============ BACKUP-REPORT=====================\n' >>  backup_info.txt")
        sudo("echo BACKUP :%s >> backup_info.txt" % backup_type)
        sudo("echo BACKUP-PATH :%s >> backup_info.txt" % path)
        if cassandra_backup:
            sudo("echo CASSANDRA-BACKUP-TYPE:%s >>  backup_info.txt" %
                cassandra_backup)
        if "No such file or directory" not in ubuntu_os:
            sudo("echo OS:%s >>  backup_info.txt" % ubuntu_os)
        if "No such file or directory" not in cent_os:
            sudo("echo OS:%s >>  backup_info.txt" % cent_os)
        sudo("echo RELEASE-VERSION:R%s >>  backup_info.txt" % release_ver)
        time = sudo('date')
        sudo("echo BACKUP TAKEN ON  :%s >>  backup_info.txt" % time)
# end of  backup_info_file


@task
def restore_cassandra_db():
    '''
    Restore the cassandra data to database nodes with following steps:
    1. Pre-check done for existence of cassandra db restore shell script.
    2. Get target backup node [can be local or remote node]
    3. Stop services and restore from the target node..
    '''

    # Check for Cassandra DB restore script in DB nodes.
    for host in env.roledefs['database']:
        with settings(host_string=host):
            if not exists('/opt/contrail/utils/cass-db-restore.sh'):
                raise AttributeError(
                    "\nRestore cassandra db script path doesnot find for the host:%s .... Aborting" %
                    host)
    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    cassandra_backup = getattr(testbed, 'cassandra_backup', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_cfgm)
        execute(stop_database)
        execute(stop_collector)
        execute(restore_cassandra, backup_data_path, store_db,cassandra_backup)
        execute(start_cfgm)
        execute(start_database)
        execute(start_collector)
    except SystemExit:
        raise SystemExit("\nRestore cassandra db Failed .... Aborting")

# end restore_cassandra_db


@task
def restore_mysql_db():
    '''
    Restore mysql data to openstack nodes with following steps:
    1. Get target backup node [can be local or remote node]
    2. Stop services and restore from the target node..
    '''

    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_nova)
        execute(stop_glance)
        execute(stop_keystone)
        execute(restore_mysql, backup_data_path, store_db)
        execute(start_nova)
        execute(start_glance)
        execute(start_keystone)
    except SystemExit:
        raise SystemExit("\nRestore Mysql db Failed .... Aborting")

# end  restore_mysql_db

@task
def restore_glance_image():
    '''
    Restore glance images data to openstack nodes with following steps:
    1. Get target backup node [can be local or remote node]
    2. Stop services and restore from the target node..
    '''

    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_glance)
        execute(restore_instance_image, backup_data_path, store_db)
        execute(start_glance)
    except SystemExit:
        raise SystemExit("\nRestore glance images data failed .... Aborting")

# end  restore_glance_image

@task
def restore_zookeeper_data():
    '''
    Restore zookeeper data to database nodes with following steps:
    1. Get target backup node [can be local or remote node]
    2. Stop services and restore from the target node..
    '''

    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_zookeeper)
        execute(restore_zookeeper, backup_data_path, store_db)
        execute(start_zookeeper)
    except SystemExit:
        raise SystemExit("\nRestore zookeeper data failed .... Aborting")

# end  restore_zookeeper_data

def change_zk_file_permission(file_path='/var/lib/zookeeper'):
    '''
    After taking the backup on different machine, /var/lib/zookeeper file ownership chnages.
    During restore on the target node, change the ownership and permission.
    '''
    if exists(file_path):
        try:
            cmd='chown -R zookeeper:zookeeper %s' %file_path
            sudo(cmd)
            cmd='chmod -R 0755  %s' %file_path
            sudo(cmd)
        except: 
            print 'failed to change owner-ship or file permission'
            raise
#end change_zk_file_permission

@task
def restore_nova_instance_data():
    '''
    Restore nova instance data to compute nodes with following steps:
    1. Get target backup node [can be local or remote node]
    2. Stop services and restore from the target node..
    '''

    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_nova_openstack_compute)
        execute(restore_instances, backup_data_path, store_db)
        execute(start_nova_openstack_compute)
        execute(reboot_nova_instance)
    except SystemExit:
        raise SystemExit("\nRestore instance data failed .... Aborting")

# end  restore_nova_instance_data


@roles('cfgm')
def restart_neutron_server():
    sudo('service neutron-server restart')
    time.sleep(5)

@roles('collector')
def restart_analytics():
    sudo('service supervisor-analytics restart')
    time.sleep(5)

@task
@roles('database', 'cfgm')
def restore_cassandra(backup_data_path='', store_db='local',cassandra_backup='full'):
    """Restore cassandra data to all databases .and usuage is restore_cassadra_db """
    global backup_path
    host = env.host_string
    msg = "Restoring backed-up DB in ({HOST}) \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
    snapshot_dir_path = '%s%s/data/' % (backup_path, host_name)
    if backup_data_path:
        if store_db == 'local':
            with settings(host_string=host):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/data/' % (host_name)
                    if exists(snapshot_path):
                        snapshot_dir_path = snapshot_path
        if store_db == 'remote':
            with settings(host_string=env.roledefs['backup'][0]):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/data/' % (host_name)
                    if exists(snapshot_path):
                        snapshot_dir_path = snapshot_path
    if store_db == 'remote':
        msg = "Restoring cassandra backed-up DB and getting  backup data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%s' % (snapshot_dir_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_cfgm)
                execute(start_database)
                execute(start_collector)
                raise SystemExit()
        with settings(host_string=host):
            with settings(warn_only=True):
                sudo('mkdir ~/contrail-data/')
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no"  -r  %s:%s  ~/contrail-data/  ' % (
                remote_host,
                remote_path)
            sudo(remote_cmd)
    with settings(host_string=host): 
        skip_key=''
        if cassandra_backup == 'custom':
                skip_key = getattr(testbed, 'skip_keyspace', None)
                if not skip_key: 
                    print "Need to Define the keyspace names in testbed.py if your are selected as custom snapshot. So that it will omit those keyspace during restoration"
                    raise SystemExit()
                skip_key = ','.join(skip_key)
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%s' % (snapshot_dir_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_cfgm)
                execute(start_database)
                execute(start_collector)
                raise SystemExit()
            snapshot_list = sudo(
                "find  %s  -name 'snapshots' " %
                snapshot_dir_path)
            snapshot_dir = snapshot_dir_path
        if store_db == 'remote':
            snapshot_list = sudo(
                "find  ~/contrail-data/data/  -name 'snapshots' ")
            snapshot_dir = '~/contrail-data/data/'
        snapshot_list = snapshot_list.split('\r\n')
        snapshot_list = snapshot_list[0]
        OS= sudo("cat /etc/os-release  | awk 'FNR == 1 {print $1 }'| awk  -F '\"' '{print $2}'") 
        if OS == 'Ubuntu' :
           snap_path = sudo(
                           "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/cassandra.yaml")
        if OS == 'CentOS' :
           snap_path = sudo(
                           "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/conf/cassandra.yaml")

        snapshot_path = snap_path.split(' ')
        db_path = snapshot_path[-1]
        if snapshot_list:
            with cd(snapshot_list):
                snapshot_name = sudo('ls -t | head -n1')
            cmd = '/opt/contrail/utils/cass-db-restore.sh -b  %s -s %s  -n %s -k %s' % (
                db_path,
                snapshot_dir,
                snapshot_name,skip_key)
            sudo(cmd)
        if store_db == 'remote':
            sudo('rm -rf  ~/contrail-data/')

# end restore_cassandra


@task
@roles('openstack')
def restore_mysql(backup_data_path, store_db='local'):
    """Restore mysql data to all openstack databases  """
    host = env.host_string
    global backup_path
    msg = "Restoring mysql backed-up DB in  ({HOST})  \n"
    with settings(host_string=host):
        host_name = sudo('hostname')
    snapshot_dir_path = '%s%s/openstack.sql' % (backup_path, host_name)
    if backup_data_path:
        if store_db == 'local':
            with settings(host_string=host):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/openstack.sql' % (host_name)
                    if exists(snapshot_path):
                        snapshot_dir_path = snapshot_path
        if store_db == 'remote':
            with settings(host_string=env.roledefs['backup'][0]):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/openstack.sql' % (host_name)
                    if exists(snapshot_path):
                        snapshot_dir_path = snapshot_path
    if store_db == 'remote':
        msg = "Restoring mysql backed-up DB and getting  backup data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%s' % (snapshot_dir_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore mysql  DB."
                execute(start_nova)
                execute(start_glance)
                execute(start_keystone)
                raise SystemExit()
        with settings(host_string=host):
            with settings(warn_only=True):
                sudo('mkdir ~/contrail-data/')
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r  %s:%s  ~/contrail-data/  ' % (
                remote_host,
                remote_path)
            sudo(remote_cmd)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%s' % (snapshot_dir_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore mysql  DB."
                execute(start_nova)
                execute(start_glance)
                execute(start_keystone)
                raise SystemExit()
        mysql_path = snapshot_dir_path
        if store_db == 'remote':
            mysql_path = '~/contrail-data/openstack.sql'
        mysql_passwd = sudo('cat /etc/contrail/mysql.token')
        mysql_cmd = 'mysql -u root --password=%s < %s' % (
            mysql_passwd, mysql_path)
        sudo(mysql_cmd)
        if store_db == 'remote':
            sudo('rm -rf  ~/contrail-data/')

# end restore_mysql

@roles('openstack')
def restore_instance_image(backup_data_path, store_db='local'):
    """Restore glance images  to all openstack nodes  """
    global backup_path
    host = env.host_string
    msg = "Restoring backed-up images  data in ({HOST}).\n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        images_path = sudo("grep  'filesystem_store_datadir'   /etc/glance/glance-api.conf | grep -v '#' ")
        images_path = images_path.split('=')
        images_path = images_path[-1]
        images_path=images_path.strip()
        images_path=images_path.split('glance')
        images_path=images_path[0]
        remote_image_path = '%s%s/' % (backup_path, host_name)
    if backup_data_path:
        if store_db == 'local':
            with settings(host_string=host):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/' % (host_name)
                    if exists('%s/' % snapshot_path):
                        remote_image_path = snapshot_path
        if store_db == 'remote':
            with settings(host_string=env.roledefs['backup'][0]):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/' % (host_name)
                    if exists('%s/' % snapshot_path):
                        remote_image_path = snapshot_path
    if store_db == 'remote':
        msg = "Restoring glance image backed-up data and getting  backup data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%sglance' % (remote_image_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore glance image data."
                execute(start_glance)
                raise SystemExit()
        execute(ssh_key_gen)
        with settings(host_string=host):
            remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress   %s:%s    %s' %(  remote_host,remote_path,images_path)
            sudo(remote_cmd)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%sglance' % (remote_image_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore glance image  data ."
                execute(start_glance)
                raise SystemExit()
            sudo('rsync -az --progress  %sglance  %s ' %
                (remote_image_path,images_path ))

  # end restore_glance_images

@roles('database', 'cfgm')
def restore_zookeeper(backup_data_path, store_db='local'):
    """Restore zookeeper data to all database nodes  """
    global backup_path
    host = env.host_string
    msg = "Restoring backed-up data in ({HOST}).\n"
    with settings(host_string=host):
        host_name = sudo('hostname')
        data_path = sudo("grep  'dataDir'   /etc/zookeeper/conf/zoo.cfg")
        zoo_path = data_path.split('=')
        zoo_path = zoo_path[-1]
        zoo_path = zoo_path.strip()
        file_path = zoo_path
        zoo_path = zoo_path.split('zookeeper')
        zoo_path = zoo_path[0]
        remote_data_path = '%s%s/' % (backup_path, host_name)
    if backup_data_path:
        if store_db == 'local':
            with settings(host_string=host):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/' % (host_name)
                    if exists('%szookeeper/' % snapshot_path):
                        remote_data_path = snapshot_path
        if store_db == 'remote':
            with settings(host_string=env.roledefs['backup'][0]):
                for bk_path in backup_data_path:
                    snapshot_path = bk_path + '%s/' % (host_name)
                    if exists('%szookeeper/' % snapshot_path):
                        remote_data_path = snapshot_path
    if store_db == 'remote':
        msg = "Restoring backed-up data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%szookeeper' % (remote_data_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore zookeeper data."
                execute(start_zookeeper)
                raise SystemExit()
        execute(ssh_key_gen)
        with settings(host_string=host):
            sudo('rm -rf %szookeeper' %zoo_path)
            remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress   %s:%s    %s' %(remote_host, remote_path, zoo_path)
            sudo(remote_cmd)
            change_zk_file_permission(file_path)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%szookeeper' % (remote_data_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore zookeeper data ."
                execute(start_zookeeper)
                raise SystemExit()
            sudo('rm -rf %szookeeper' %zoo_path)
            sudo('rsync -az --progress  %s  %s ' % (remote_path, zoo_path ))

  # end restore_zookeeper


@roles('compute')
def restore_instances(backup_data_path, store_db='local'):
    """Restore instances data to all compute nodes  """
    global backup_path
    host = env.host_string
    tsn_nodes = []
    tor_nodes = []
    if 'tsn' in env.roledefs:
        tsn_nodes = env.roledefs['tsn']
    if 'toragent' in env.roledefs:
        tor_nodes = env.roledefs['toragent']
    if host not in (tsn_nodes and tor_nodes) :
        msg = "Restoring backed-up instances data in ({HOST}).\n"
        with settings(host_string=host):
            host_name = sudo('hostname')
            insta_path = sudo("grep  '^state_path'   /etc/nova/nova.conf")
        instances_path = insta_path.split('=')
        instances_path = instances_path[-1]
        instances_path = instances_path.strip()
        remote_instances_dir_path = '%s%s/' % (backup_path, host_name)
        if backup_data_path:
            if store_db == 'local':
                with settings(host_string=host):
                    for bk_path in backup_data_path:
                        snapshot_path = bk_path + '%s/' % (host_name)
                        if exists('%sinstances/' % snapshot_path):
                            remote_instances_dir_path = snapshot_path
            if store_db == 'remote':
                with settings(host_string=env.roledefs['backup'][0]):
                    for bk_path in backup_data_path:
                        snapshot_path = bk_path + '%s/' % (host_name)
                        if exists('%sinstances/' % snapshot_path):
                            remote_instances_dir_path = snapshot_path
        if store_db == 'remote':
            msg = "Restoring instances backed-up  data and getting  backup data from remote host:({HOST}) \n"
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
            remote_path = '%sinstances' % (remote_instances_dir_path)
            with settings(host_string=env.roledefs['backup'][0]):
                if not exists(remote_path):
                    print "Remote path doesnot exist ... So aborting the restore nova instances data."
                    execute(start_nova_openstack_compute)
                    raise SystemExit()
            execute(ssh_key_gen)
            with settings(host_string=host):
                remote_cmd='rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress   %s:%s    %s/' %(  remote_host,remote_path,instances_path)
                sudo(remote_cmd)
        with settings(host_string=host):
            if store_db == 'local':
                print (msg.format(HOST=host_name))
                remote_path = '%sinstances' % (remote_instances_dir_path)
                if not exists(remote_path):
                    print "Remote path doesnot exist ... So aborting the restore nova instaces data ."
                    execute(start_nova_openstack_compute)
                    raise SystemExit()
                sudo('rsync -az --progress  %sinstances  %s/ ' %
                    (remote_instances_dir_path,instances_path ))

  # end restore_instances


def ssh_key_gen():
    host = env.host_string
    with settings(host_string=host):
        if not exists('~/.ssh/id_rsa.pub'):
            sudo('ssh-keygen  -f ~/.ssh/id_rsa  -t rsa -N "" -q ')
        key = get('~/.ssh/id_rsa.pub', '/tmp/')
    with settings(host_string=env.roledefs['backup'][0]):
        with settings(warn_only=True):
            sudo('mkdir /pub-key/')
        put(key[0], '/pub-key/', use_sudo=True)
        if not exists('~/.ssh/'):
            sudo('mkdir ~/.ssh/')
        with cd('/pub-key/'):
            sudo('cat id_rsa.pub >~/.ssh/authorized_keys')
        sudo('chmod 700 ~/.ssh/authorized_keys')
        sudo('rm -rf /pub-key/')

# end ssh_key_gen


def replace_key(text, skip_key):
    for key in skip_key:
        text=re.sub('\\b'+key+'\\b','',text)
    return text
# end replace_kespace_for_custom_cassandra_snapshot

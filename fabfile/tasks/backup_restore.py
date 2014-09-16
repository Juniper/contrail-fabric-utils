from .fabfile.config import *
from .fabfile.utils.fabos import *
from .fabfile.utils.host import *
from fabric.contrib.files import exists
from .fabfile.utils.fabos import detect_ostype
from .fabfile.tasks.services import *
import string

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
    3.Instances_data
    '''
    try:
        execute(backup_cassandra_db)
        execute(backup_mysql_db)
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
    3.Instances_data
    '''
    try:
        execute(restore_cassandra_db)
        execute(restore_mysql_db)
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


@roles('database')
def backup_cassandra(db_datas, store_db='local', cassandra_backup='full'):
    """Backup cassandra data to all databases  """
    global backup_path, final_dir
    host = env.host_string
    msg = "Processing the Cassandra DB backup and default path for backup DB data is ~/contrail_bkup_data/hostname/data/ in ({HOST})  \n"
    with settings(host_string=host):
        host_name = run('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing the Cassandra DB Backup and puting DB dabckup data into remote host:({HOST}) and default path is /root/contrail_bkup_data/hostname/data/ or backup path is defined  as per testbed.py file  \n "
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        snap_path = run(
            "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/cassandra.yaml")
        snapshot_path = snap_path.split(' ')
        db_path = snapshot_path[-1]
        execute(verify_disk_space, db_datas, db_path, store_db)
        dir_name = '%s%s/' % (backup_path, host_name)
        if db_datas:
            dir_name = final_dir + '%s/' % (host_name)
        if exists('backup_info.txt'):
            run('rm -rf backup_info.txt')
        with cd(db_path):
            skip_key = getattr(testbed, 'skip_keyspace', None)
            if not skip_key:
                print "Need to Define the keyspace names in testbed.py if your are selected as custom snapshot. So that it will omit those keyspace name during the  database snapshot"
                raise SystemExit()
            cs_key = run('ls')
            cs_key = cs_key.translate(string.maketrans("\n\t\r", "   "))
            custom_key = replace_key(cs_key, skip_key)
        nodetool_cmd = 'nodetool -h localhost -p 7199 snapshot'
        if cassandra_backup == 'custom':
            nodetool_cmd = 'nodetool -h localhost -p 7199 snapshot %s ' % custom_key
        run(nodetool_cmd)
        snapshot_list = run("find %s/  -name 'snapshots' " % db_path)
        snapshot_list = snapshot_list.split('\r\n')
        snapshot_list = snapshot_list[0]
        with cd(snapshot_list):
            snapshot_name = run('ls -t | head -n1')
        print "Cassandra DB Snapshot Name: %s" % (snapshot_name)
        if store_db == 'local':
            run('cp -R  %s  %s ' % (db_path, dir_name))
        execute(backup_info_file, dir_name, backup_type='Cassandra')
        if store_db == 'local':
            run('cp backup_info.txt %s' % dir_name)
        if store_db == 'remote':
            execute(ssh_key_gen)
            source_path = '%s   backup_info.txt' % (db_path)
            remote_path = '%s' % (dir_name)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r  %s  %s:%s' % (
                source_path,
                remote_host,
                remote_path)
            run(remote_cmd)

# end backup_cassandra


@roles('openstack')
def backup_mysql(db_datas, store_db='local'):
    """Backup mysql data to all opentstack databases and usuage is fab backup_mysql_db """
    host = env.host_string
    global backup_path, final_dir
    msg = "Processing Mysql DB backup and default path for backup data is ~/contrail_bkup_data/hostname/openstack.sql in ({HOST}) \n"
    with settings(host_string=host):
        host_name = run('hostname')
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
        mysql_passwd = run('cat /etc/contrail/mysql.token')
        mysql_cmd = 'mysqldump  -u root --password=%s --all-databases  > openstack.sql' % (
            mysql_passwd)
        run(mysql_cmd)
        if store_db == 'local':
            run('cp openstack.sql  %s ' % remote_dir_name)
        execute(backup_info_file, remote_dir_name, backup_type='Mysql')
        if store_db == 'local':
            run('cp backup_info.txt  %s' % remote_dir_name)
        if store_db == 'remote':
            remote_path = '%s ' % (remote_dir_name)
            source_path = 'openstack.sql  backup_info.txt'
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r   %s  %s:%s' % (
                         source_path,
                remote_host,
                remote_path)
            run(remote_cmd)

# end backup_mysql


@roles('compute')
def backup_instances(db_datas, store_db='local'):
    """Backup instances data to all compute nodes """
    host = env.host_string
    global backup_path, final_dir
    msg = "Processing instances backup and default path for backup data is ~/contrail_bkup_data/hostname/instances  in ({HOST}) \n"
    with settings(host_string=host):
        host_name = run('hostname')
        if store_db == 'local':
            print (msg.format(HOST=host_name))
        if store_db == 'remote':
            msg = "Processing instances data Backup and puting instances backup data into remote host:({HOST}) and default path is ~/contrail_bkup_data/hostname/instances or backup path is defined as per testbed.py file \n"
            remote_host = env.roledefs['backup'][0]
            print (msg.format(HOST=remote_host))
        insta_path = run("grep  'state_path'   /etc/nova/nova.conf")
        instances_path = insta_path.split('=')
        instances_path = instances_path[-1]
        db_path = instances_path
        execute(verify_disk_space, db_datas, db_path, store_db)
        remote_instances_path = '%s%s/' % (backup_path, host_name)
        if db_datas:
            remote_instances_path = final_dir + '%s/' % (host_name)
        if store_db == 'local':
            run(
                'cp -r %s/instances/ %s ' %
                (instances_path, remote_instances_path))
        execute(
            backup_info_file,
            remote_instances_path,
            backup_type='Instances')
        if store_db == 'local':
            run('cp backup_info.txt %s' % remote_instances_path)
        if store_db == 'remote':
            remote_path = '%s' % (remote_instances_path)
            source_path = '%s/instances/   backup_info.txt' % (instances_path)
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r  %s  %s:%s' % (
                source_path,
                remote_host,
                remote_path)
            run(remote_cmd)

# end backup_instances


def verify_disk_space(db_datas, db_path, store_db):
    host = env.host_string
    global backup_path, final_dir
    final_bk_dir = []
    with settings(host_string=host):
        host_name = run('hostname')
        with cd(db_path):
            usage_dk_space = run("du -ck  $PWD | grep 'total'")
            make_avail = run("du -ckh  $PWD | grep 'total'")
            usage_dk_space = usage_dk_space.split('\t')
            usage_dk_space = int(usage_dk_space[0])
            used_dk_space = usage_dk_space * 1.2
        if store_db == 'local':
            if not db_datas:
                with settings(warn_only=True):
                    run('mkdir %s' % backup_path)
                    run('mkdir %s%s' % (backup_path, host_name))
                with cd('%s%s' % (backup_path, host_name)):
                    free_dk_space = run(
                        "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                    free_dk_space = int(free_dk_space)
            if db_datas:
                for get_dir in db_datas:
                    with cd('%s' % get_dir):
                        free_dk_space = run(
                            "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                        free_dk_space = int(free_dk_space)
                        if free_dk_space >= used_dk_space:
                            final_bk_dir.append(get_dir)
                with settings(warn_only=True):
                    run('mkdir %s%s/ ' % (final_bk_dir[0], host_name))
                final_dir = final_bk_dir[0]
    if store_db == 'remote':
        remote_host = env.roledefs['backup'][0]
        with settings(host_string=env.roledefs['backup'][0]):
            if not db_datas:
                with settings(warn_only=True):
                    run('mkdir %s' % backup_path)
                    run('mkdir %s%s' % (backup_path, host_name))
                with cd('%s%s' % (backup_path, host_name)):
                    free_dk_space = run(
                        "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                    free_dk_space = int(free_dk_space)
            if db_datas:
                for get_dir in db_datas:
                    with cd('%s' % get_dir):
                        free_dk_space = run(
                            "df  $PWD | awk '/[0-9]%/{print $(NF-2)}'")
                        free_dk_space = int(free_dk_space)
                        if free_dk_space >= used_dk_space:
                            final_bk_dir.append(get_dir)
                with settings(warn_only=True):
                    run('mkdir %s%s/ ' % (final_bk_dir[0], host_name))
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
        ubuntu_os = run(
            "cat /etc/lsb-release | awk 'FNR == 1 {print}' | cut -d '=' -f2")
        cent_os = run("cat /etc/system-release |  awk  '{print $1 $2}'")
        relese_ver = run(
            "contrail-version | grep 'contrail-install-packages' | awk  '{print $2}'")
        run("echo '============ BACKUP-REPORT=====================\n' >>  backup_info.txt")
        run("echo BACKUP :%s >> backup_info.txt" % backup_type)
        run("echo BACKUP-PATH :%s >> backup_info.txt" % path)
        if cassandra_backup:
            run("echo CASSANDRA-BACKUP-TYPE:%s >>  backup_info.txt" %
                cassandra_backup)
        if "No such file or directory" not in ubuntu_os:
            run("echo OS:%s >>  backup_info.txt" % ubuntu_os)
        if "No such file or directory" not in cent_os:
            run("echo OS:%s >>  backup_info.txt" % cent_os)
        run("echo RELEASE-VERSION:R%s >>  backup_info.txt" % relese_ver)
        time = run('date')
        run("echo BACKUP TAKEN ON  :%s >>  backup_info.txt" % time)
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
            if not exists('/opt/contrail/utils/cass-db-restore-v5.sh'):
                raise AttributeError(
                    "\nRestore cassandra db script path doesnot find for the host:%s .... Aborting" %
                    host)
    backup_node = getattr(testbed, 'backup_node', None)
    backup_data_path = getattr(testbed, 'backup_db_path', None)
    store_db = 'local'
    if backup_node:
        store_db = 'remote'

    try:
        execute(stop_cfgm)
        execute(stop_database)
        execute(stop_collector)
        execute(restore_cassandra, backup_data_path, store_db)
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


@task
@roles('database')
def restore_cassandra(backup_data_path='', store_db='local'):
    """Restore cassandra data to all databases .and usuage is restore_cassadra_db """
    global backup_path
    host = env.host_string
    msg = "Processing Restore Cassandra DB backup in ({HOST}) \n"
    with settings(host_string=host):
        host_name = run('hostname')
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
        msg = "Processing Restore Cassandra  DB and getting  DB dabckup data from remote host:({HOST}) \n"
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
                run('mkdir ~/contrail-data/')
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no"  -r  %s:%s  ~/contrail-data/  ' % (
                remote_host,
                remote_path)
            run(remote_cmd)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%s' % (snapshot_dir_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_cfgm)
                execute(start_database)
                execute(start_collector)
                raise SystemExit()
            snapshot_list = run(
                "find  %s  -name 'snapshots' " %
                snapshot_dir_path)
            snapshot_dir = snapshot_dir_path
        if store_db == 'remote':
            snapshot_list = run(
                "find  ~/contrail-data/data/  -name 'snapshots' ")
            snapshot_dir = '~/contrail-data/data/'
        snapshot_list = snapshot_list.split('\r\n')
        snapshot_list = snapshot_list[0]
        snap_path = run(
            "grep  -A 1  'data_file_directories:' --after-context=1  /etc/cassandra/cassandra.yaml")
        snapshot_path = snap_path.split(' ')
        db_path = snapshot_path[-1]
        if snapshot_list:
            with cd(snapshot_list):
                snapshot_name = run('ls -t | head -n1')
            cmd = '/opt/contrail/utils/cass-db-restore-v5.sh -b  %s -s %s  -n %s' % (
                db_path,
                snapshot_dir,
                snapshot_name)
            run(cmd)
        if store_db == 'remote':
            run('rm -rf  ~/contrail-data/')

# end restore_cassandra


@task
@roles('openstack')
def restore_mysql(backup_data_path, store_db='local'):
    """Restore mysql data to all openstack databases  """
    host = env.host_string
    global backup_path
    msg = "Processing Restore Mysql DB backup in  ({HOST})  \n"
    with settings(host_string=host):
        host_name = run('hostname')
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
        msg = "Processing Mysql restore DB and getting  DB dabckup data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%s' % (snapshot_dir_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_nova)
                execute(start_glance)
                execute(start_keystone)
                raise SystemExit()
        with settings(host_string=host):
            with settings(warn_only=True):
                run('mkdir ~/contrail-data/')
            execute(ssh_key_gen)
            remote_cmd = 'scp -o "StrictHostKeyChecking no" -r  %s:%s  ~/contrail-data/  ' % (
                remote_host,
                remote_path)
            run(remote_cmd)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%s' % (snapshot_dir_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_nova)
                execute(start_glance)
                execute(start_keystone)
                raise SystemExit()
        mysql_path = snapshot_dir_path
        if store_db == 'remote':
            mysql_path = '~/contrail-data/openstack.sql'
        mysql_passwd = run('cat /etc/contrail/mysql.token')
        mysql_cmd = 'mysql -u root --password=%s < %s' % (
            mysql_passwd, mysql_path)
        run(mysql_cmd)
        if store_db == 'remote':
            run('rm -rf  ~/contrail-data/')

# end restore_mysql


@roles('compute')
def restore_instances(backup_data_path, store_db='local'):
    """Restore instances data to all compute nodes  """
    global backup_path
    host = env.host_string
    msg = "Processing  Restore instances backup in ({HOST}).\n"
    with settings(host_string=host):
        host_name = run('hostname')
        insta_path = run("grep  'state_path'   /etc/nova/nova.conf")
    instances_path = insta_path.split('=')
    instances_path = instances_path[-1]
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
        msg = "Processing restore instances data and getting  backup data from remote host:({HOST}) \n"
        remote_host = env.roledefs['backup'][0]
        print (msg.format(HOST=remote_host))
        remote_path = '%sinstances' % (remote_instances_dir_path)
        with settings(host_string=env.roledefs['backup'][0]):
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_nova_openstack_compute)
                raise SystemExit()
        execute(ssh_key_gen)
        with settings(host_string=host):
            with settings(warn_only=True):
                run('mkdir ~/contrail-data/')
            remote_cmd = 'scp -o "StrictHostKeyChecking no"  -r   %s:%s   ~/contrail-data/  ' % (
                remote_host,
                remote_path)
            run(remote_cmd)
    with settings(host_string=host):
        if store_db == 'local':
            print (msg.format(HOST=host_name))
            remote_path = '%sinstances' % (remote_instances_dir_path)
            if not exists(remote_path):
                print "Remote path doesnot exist ... So aborting the restore cassandra DB."
                execute(start_nova_openstack_compute)
                raise SystemExit()
        backup_path = remote_instances_dir_path
        if store_db == 'remote':
            backup_path = '~/contrail-data/'
        run('cp -r   %sinstances/   %s/  ' % (backup_path, instances_path))
        run('find %s/instances/  -type f -exec chmod 777 {} \;' %
            instances_path)
        if store_db == 'remote':
            run('rm -rf  ~/contrail-data/')

  # end restore_instances


def ssh_key_gen():
    host = env.host_string
    with settings(host_string=host):
        if not exists('~/.ssh/id_rsa.pub'):
            run('ssh-keygen  -f ~/.ssh/id_rsa  -t rsa -N "" -q ')
        key = get('~/.ssh/id_rsa.pub', '/tmp/')
    with settings(host_string=env.roledefs['backup'][0]):
        with settings(warn_only=True):
            run('mkdir /pub-key/')
        put(key[0], '/pub-key/')
        if not exists('~/.ssh/'):
            run('mkdir ~/.ssh/')
        with cd('/pub-key/'):
            run('cat id_rsa.pub >~/.ssh/authorized_keys')
        run('chmod 700 ~/.ssh/authorized_keys')

# end ssh_key_gen


def replace_key(text, skip_key):
    for key in skip_key:
        text = text.replace(key, "")
    return text
# end replace_kespace_for_custom_cassandra_snapshot

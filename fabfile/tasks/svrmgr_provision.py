import json
import string
import textwrap
import pdb
import tempfile
import os
import re
from datetime import datetime as dt


from fabfile.utils.host import verify_sshd
from fabfile.tasks.verify import *
#from fabfile.tasks.helpers import *
from time import sleep
from fabric.state import connections



SERVER_BOOT_TIME=60
SERVER_RETRY_TIME=1000



@task
@EXECUTE_TASK
def svrmgr_reimage_all():
    """ using svrmgr, reimage all the nodes """

    pdb.set_trace()
    image_id = get_image_id()
    pkg_id = get_pkg_id()
    vns_id = get_vns_id()

    with  settings(host_string=env.svrmgr, warn_only=True):

        run('server-manager show all | python -m json.tool')
        run('server-manager reimage --package_image_id %s --vns_id %s  %s' %(pkg_id,vns_id,image_id))

    sleep(SERVER_BOOT_TIME)

    user = "root"
    server_state = {}

    in_file = open( env.server_file, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    for retry in range(SERVER_RETRY_TIME):
      server_ip = {}
      for  node in server_dict['server']:
        server_ip = node['ip']
        if not verify_sshd(server_ip, user, env.password):
           sleep(1)
           print "Node %s not reachable....retrying" %(server_ip)
           server_state[server_ip] = False
        else:
           print "Node %s is UP" %(server_ip)
           if  server_state[server_ip] == False:
               target_node = '%s@%s' %(user,server_ip)
               with settings( host_string = target_node ):
                   connections.connect(env.host_string)
               with settings( host_string = target_node ) :
                   output = run('uptime')
                   uptime = int(output.split()[2])
                   if uptime > 2 :
                       raise RuntimeError('Restart failed for Host (%s)' %server_ip)
                   else :
                       print "Node %s has rebooted and UP now" %(server_ip)
                       output = run('dpkg -l | grep contrail')
                       match = re.search('contrail-fabric-utils\s+(\S+)\s+', output, re.M)
                       if pkg_id not in match.group(1) :
                           raise RuntimeError('Reimage not able to download package %s on targetNode (%s)' \
                                              %(pkg_id, server_ip) )
                       match = re.search('contrail-install-packages\s+(\S+)\s+', output, re.M)
                       if pkg_id not in match.group(1) :
                           raise RuntimeError('Reimage not able to download package %s on targetNode (%s)' \
                                              %(pkg_id, server_ip) )
                       server_state[server_ip] = True

      #End for  node in server_dict['server']:
      
      result = True
      for key in server_state:
        result = result and server_state[key]

      if result == True:
        break
      #End for key in env.server:

    #End for retry in range(SERVER_RETRY_TIME):

    if not result:
        raise RuntimeError('Unable to SSH to one or more Host ' )



@task
@EXECUTE_TASK
def svrmgr_add_all():
    """ Add vns , image , server detail to svrmgr database. """
    pdb.set_trace()
    add_vns()
    add_image()
    add_pkg()
    add_json()
    add_server()



@task
@EXECUTE_TASK
def svrmgr_provision_all():
    """ using svrmgr, provision the vns  """

    image_id = get_image_id()
    pkg_id = get_pkg_id()
    vns_id = get_vns_id()

    with  settings(host_string=env.svrmgr, warn_only=True):

        run('server-manager provision --vns_id %s %s' %(vns_id,pkg_id) )
        run('server-manager show all | python -m json.tool')



@task
def add_json():

    timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    local( 'cp %s %s.org.%s' %(env.server_file, env.server_file, timestamp) )

    in_file = open( env.server_file, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    for  node in server_dict['server']:
      roles = []
      for key in env.roledefs:

        if key == 'all' or key == 'build' :
          continue

        for  host_string in env.roledefs[key]:
          ip = getIp(host_string)
          if node['ip'] == ip:
            if key == 'cfgm':
                roles.append("config")
            else:
                roles.append(key)

      if not len(roles):
        node['roles'] = [ "compute" ]
            
      else:
        node['roles'] =  roles 
      
    out_file = open(env.server_file, 'w')
    out_data = json.dumps(server_dict)
    out_file.write(out_data)
    out_file.close()


def getIp(string) :

   regEx = re.compile( '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}' )
   result = regEx.search(string)

   if result:
     return result.group()
   else:
     return  None


def get_image_id() :

    image_file = open( env.image_file, 'r' )
    image_data = image_file.read()
    image_json = json.loads(image_data)
    image_id = image_json['image'][0]['image_id']
    image_file.close()

    return image_id


def get_pkg_id() :

    pkg_file = open( env.pkg_file, 'r' )
    pkg_data = pkg_file.read()
    pkg_json = json.loads(pkg_data)
    pkg_id = pkg_json['image'][0]['image_id']
    pkg_file.close()

    return pkg_id



def get_vns_id() :

    vns_file = open( env.vns_file, 'r' )
    vns_data = vns_file.read()
    vns_json = json.loads(vns_data)
    vns_id = vns_json['vns'][0]['vns_id']
    vns_file.close()

    return vns_id



def add_vns():

    with  settings(host_string=env.svrmgr):
        with settings(warn_only=True):

            file_name = os.path.basename(env.vns_file)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(env.vns_file, '%s/%s' % (temp_dir, file_name))

            run('server-manager add  vns -f %s/%s' %(temp_dir, file_name) )
            run('server-manager show all | python -m json.tool')

def add_image():

    with  settings(host_string=env.svrmgr):
        with settings(warn_only=True):

            file_name = os.path.basename(env.image_file)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(env.image_file, '%s/%s' % (temp_dir, file_name))

            run('server-manager add  image -f %s/%s' %(temp_dir, file_name) )
            run('server-manager show all | python -m json.tool')

def add_pkg():

    with  settings(host_string=env.svrmgr):
        with settings(warn_only=True):

            file_name = os.path.basename(env.pkg_file)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(env.pkg_file, '%s/%s' % (temp_dir, file_name))

            run('server-manager add  image -f %s/%s' %(temp_dir, file_name) )
            run('server-manager show all | python -m json.tool')


def add_server():

    with  settings(host_string=env.svrmgr):
        with settings(warn_only=True):

            file_name = os.path.basename(env.server_file)
            temp_dir= tempfile.mkdtemp()
            run('mkdir -p %s' % temp_dir)
            put(env.server_file, '%s/%s' % (temp_dir, file_name))

            run('server-manager add  server -f %s/%s' %(temp_dir, file_name) )
            run('server-manager show all | python -m json.tool')


@task
@EXECUTE_TASK
def svrmgr_verify_all_roles():

    execute(verify_database)
    execute(verify_cfgm)
    execute(verify_control)
    execute(verify_collector)
    execute(verify_webui)
    execute(verify_compute)



import shutil
import tempfile
from ConfigParser import SafeConfigParser

from fabfile.config import *

def get_value(src_file, section, variable):
    '''Retrieve value of given variable in the specified config file
       from the first openstack node
    '''
    temp_dir = tempfile.mkdtemp()
    dest_file = '%s/openstack_nova.conf' % temp_dir
    print 'INFO: Retrieve (%s) file from (%s) and copy to (%s)' %  (
           src_file,
           '%s' % env.host_string,
           dest_file)
    status = get(src_file, dest_file)
    # Parse file and retrieve secret
    parser = SafeConfigParser()
    read_files = parser.read(dest_file)
    if dest_file not in read_files:
        raise RuntimeError('ERROR: Unable to parse (%s) ...' % dest_file)
    section_vars = dict(parser.items(section))
    shutil.rmtree(temp_dir)
    return section_vars.get(variable)

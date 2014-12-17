import os
import shutil
import tempfile
import ConfigParser
from ConfigParser import SafeConfigParser
from fabos import get_as_sudo

from fabfile.config import *

def get_value(src_file, section, *variables, **kwargs):
    '''Retrieve value of given variables in the specified config file
       from the node
    '''
    values = []
    raw = kwargs.get('raw', True)
    temp_dir = tempfile.mkdtemp()
    dest_file = '%s/%s' % (temp_dir, os.path.basename(src_file))
    print 'INFO: Retrieve (%s) file from (%s) and copy to (%s)' %  (
           src_file,
           '%s' % env.host_string,
           dest_file)
    status = get_as_sudo(src_file, dest_file)
    # Parse file and retrieve values
    parser = SafeConfigParser()
    read_files = parser.read(dest_file)
    if dest_file not in read_files:
        raise RuntimeError('ERROR: Unable to parse (%s) ...' % dest_file)
    for variable_name in variables:
        try:
            values.append(parser.get(section, variable_name, raw=raw))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as err:
            print "WARNING: Exception (%s) during retrieving (%s)"\
                  " from section (%s)" % (err, variable_name, section)
            values.append(None)
    shutil.rmtree(temp_dir)
    return values[0] if len(values) == 1 else values

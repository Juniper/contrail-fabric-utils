from fabfile.config import *

@task
@roles('all')
def get_all_time():
    date = sudo("DATE=$( date ); DATEMILLISEC=$( date +%s ); echo $DATE; echo $DATEMILLISEC")
    return tuple(date.split('\r\n'))

@task
@roles('build')
def verify_time_all():
    result = execute('get_all_time')
    print result
    all_time = [int(date_in_millisec) for date, date_in_millisec in result.values()]
    all_time.sort()
   
    if (all_time[-1] - all_time[0]) > 120:
        raise RuntimeError("Time not synced in the nodes, Please sync and proceed:\n %s" % result)
    else:
        print "Time synced in the nodes, Proceeding to install/provision."

     

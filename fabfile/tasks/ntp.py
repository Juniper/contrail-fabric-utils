from fabfile.config import *

@task
@roles('all')
def get_all_time():
    date = sudo("DATE=$( date ); DATEMILLISEC=$( date +%s ); echo $DATE; echo $DATEMILLISEC")
    return tuple(date.split('\r\n'))

@task
@parallel
@roles('build')
def verify_time_all():
    result = execute('get_all_time')
    all_time = []
    for dates in result.values():
        try:
            (date, date_in_millisec) = dates
            all_time.append(int(date_in_millisec))
        except ValueError:
            print "ERROR: %s" %  dates
    all_time.sort()

    if (all_time[-1] - all_time[0]) > 240:
        raise RuntimeError("Time not synced in the nodes,"
                           " Please sync and proceed:\n %s %s %s" %
                           (result, all_time[-1], all_time[0]))
    else:
        print "Time synced in the nodes, Proceeding to install/provision."

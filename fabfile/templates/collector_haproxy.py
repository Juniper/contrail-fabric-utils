import string

template = string.Template("""#contrail-collector-marker-start
$__contrail_collector_stats__
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__contrail_analytics_api__
    default_backend    contrail-analytics-api

backend contrail-analytics-api
    option nolinger
    timeout server 3m
    balance     roundrobin
$__contrail_analytics_api_backend_servers__

#contrail-collector-marker-end
""")

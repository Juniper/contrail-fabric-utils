import string

template = string.Template("""#contrail-collector-marker-start
listen contrail-collector-stats
   bind :5938
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend  contrail-analytics-api
    bind *:8081
    default_backend    contrail-analytics-api

backend contrail-analytics-api
    option nolinger
    timeout server 3m
    balance     roundrobin
$__contrail_analytics_api_backend_servers__

#contrail-collector-marker-end
""")

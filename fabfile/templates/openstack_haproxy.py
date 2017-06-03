import string

template = string.Template("""#contrail-openstack-marker-start
$__contrail_openstack_stats__
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__keystone_frontend__
    default_backend    keystone-backend

backend keystone-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__keystone_tcp_check_lines__

$__keystone_backend_servers__

$__keystone_admin_frontend__
    default_backend    keystone-admin-backend

backend keystone-admin-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance    roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__keystone_admin_tcp_check_lines__

$__keystone_admin_backend_servers__

$__openstack_glance__
    default_backend    glance-backend

backend glance-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__glance_tcp_check_lines__
$__glance_backend_servers__

$__openstack_heat_api__
    default_backend    heat-api-backend 
backend heat-api-backend 
    option tcpka 
    option nolinger 
    timeout server 24h 
    balance   roundrobin 
    option tcp-check 
    tcp-check connect port 3306 
    default-server error-limit 1 on-error mark-down 
    option tcp-check 
    option httpchk 
    tcp-check connect port 3337 
    tcp-check send Host:localhost 
    http-check expect ! rstatus ^5 
    default-server error-limit 1 on-error mark-down 
$__heat_api_tcp_check_lines__
$__heat_backend_servers__

$__openstack_cinder__
    default_backend  cinder-backend

backend cinder-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin
$__cinder_backend_servers__

$__ceph_rest_api_server__
    default_backend  ceph-rest-api-server-backend

backend ceph-rest-api-server-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin
$__ceph_restapi_backend_servers__


$__openstack_nova_api__
    default_backend  nova-api-backend

backend nova-api-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__nova_api_tcp_check_lines__

$__nova_api_backend_servers__

$__openstack_nova_meta__
    default_backend  nova-meta-backend

backend nova-meta-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__nova_meta_tcp_check_lines__

$__nova_meta_backend_servers__

$__openstack_nova_vnc__
    default_backend  nova-vnc-backend

backend nova-vnc-backend
    option tcpka
    option nolinger
    timeout server 5h
    balance  roundrobin
    $__nova_vnc_backend_servers__

$__openstack_barbican__
    default_backend    barbican-backend

backend barbican-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance roundrobin

    option tcp-check
    tcp-check connect port 3306
    default-server error-limit 1 on-error mark-down

    option tcp-check
    option httpchk
    tcp-check connect port 3337
    tcp-check send Host:localhost
    http-check expect ! rstatus ^5
    default-server error-limit 1 on-error mark-down

$__barbican_tcp_check_lines__ 

$__barbican_backend_servers__

$__memcache__
   mode tcp
   balance roundrobin
   option tcplog
   maxconn 10000                                                                                   
   balance roundrobin                                                                              
   option tcpka                                                                                    
   option nolinger                                                                                 
   timeout connect 5s                                                                              
   timeout client 0
   timeout server 0
$__memcached_servers__

$__rabbitmq__
    mode tcp
    maxconn 10000
    balance leastconn
    option tcpka
    option nolinger
    option forceclose
    timeout client 0
    timeout server 0
    timeout client-fin 60s
    timeout server-fin 60s
$__rabbitmq_servers__

$__mysql__
    mode tcp
    balance leastconn
    option tcpka
    option nolinger
    option forceclose
    maxconn 10000
    timeout connect 30s
    timeout client 0
    timeout server 0
    timeout client-fin 60s
    timeout server-fin 60s
$__mysql_servers__

#contrail-openstack-marker-end
""")

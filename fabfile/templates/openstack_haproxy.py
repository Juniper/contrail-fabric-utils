import string

template = string.Template("""#contrail-openstack-marker-start
listen contrail-openstack-stats :5936
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend openstack-keystone *:5000
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

    option tcp-check
    tcp-check connect port 6000
    default-server error-limit 1 on-error mark-down

$__keystone_backend_servers__

frontend openstack-keystone-admin *:35357
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

    option tcp-check
    tcp-check connect port 35358
    default-server error-limit 1 on-error mark-down

$__keystone_admin_backend_servers__

frontend openstack-glance *:9292
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

    option tcp-check
    tcp-check connect port 9393
    default-server error-limit 1 on-error mark-down
$__glance_backend_servers__

frontend openstack-heat-api *:8004 
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
    option tcp-check 
    tcp-check connect port 8005 
    default-server error-limit 1 on-error mark-down 
$__heat_backend_servers__

frontend openstack-cinder *:8776
    default_backend  cinder-backend

backend cinder-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin
$__cinder_backend_servers__

frontend ceph-rest-api-server *:5005
    default_backend  ceph-rest-api-server-backend

backend ceph-rest-api-server-backend
    option tcpka
    option nolinger
    timeout server 24h
    balance   roundrobin
$__ceph_restapi_backend_servers__


frontend openstack-nova-api *:8774
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

    option tcp-check
    tcp-check connect port 9774
    default-server error-limit 1 on-error mark-down

$__nova_api_backend_servers__

frontend openstack-nova-meta *:8775
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

    option tcp-check
    tcp-check connect port 9775
    default-server error-limit 1 on-error mark-down

$__nova_meta_backend_servers__

frontend openstack-nova-vnc *:6080
    default_backend  nova-vnc-backend

backend nova-vnc-backend
    option tcpka
    option nolinger
    timeout server 5h
    balance  roundrobin
    $__nova_vnc_backend_servers__

listen memcached 0.0.0.0:11222
   mode tcp
   balance roundrobin
   option tcplog
   maxconn 10000                                                                                   
   balance roundrobin                                                                              
   option tcpka                                                                                    
   option nolinger                                                                                 
   timeout connect 5s                                                                              
   timeout client 48h                                                                              
   timeout server 48h 
$__memcached_servers__

listen  rabbitmq 0.0.0.0:5673
    mode tcp
    maxconn 10000
    balance leastconn
    option tcpka
    option nolinger
    option forceclose
    timeout client 48h
    timeout server 48h
    timeout client-fin 60s
    timeout server-fin 60s
$__rabbitmq_servers__

listen  mysql 0.0.0.0:33306
    mode tcp
    balance leastconn
    option tcpka
    option nolinger
    option forceclose
    maxconn 10000
    timeout connect 30s
    timeout client 24h
    timeout server 24h
    timeout client-fin 60s
    timeout server-fin 60s
$__mysql_servers__

#contrail-openstack-marker-end
""")

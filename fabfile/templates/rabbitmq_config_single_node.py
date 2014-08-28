import string

template = string.Template("""[
   {rabbit, [ {tcp_listeners, [{"$__control_intf_ip__", 5672}]},
   {loopback_users, []},
   {log_levels,[{connection, info},{mirroring, info}]} ]
    }
].""")

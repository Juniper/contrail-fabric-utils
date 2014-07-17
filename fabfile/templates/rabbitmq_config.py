import string

template = string.Template("""[
   {rabbit, [ {tcp_listeners, [{"$__control_intf_ip__", 5672}]}, {cluster_partition_handling, autoheal},{loopback_users, []},
              {cluster_nodes, {[$__rabbit_hosts__], disc}},
              {vm_memory_high_watermark, 0.4},
              {disk_free_limit,50000000},
              {log_levels,[{connection, info},{mirroring, info}]},
              {heartbeat,600},
              {delegate_count,20}
            ]
   }
].""")

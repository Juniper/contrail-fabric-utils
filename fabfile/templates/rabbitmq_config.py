import string

template = string.Template("""[
   {rabbit, [ {tcp_listeners, [{"$__control_intf_ip__", 5672}]}, {cluster_partition_handling, autoheal},{loopback_users, []},
              {cluster_nodes, {[$__rabbit_hosts__], disc}},
              {vm_memory_high_watermark, 0.4},
              {disk_free_limit,50000000},
              {log_levels,[{connection, info},{mirroring, info}]},
              {delegate_count,20},
              {channel_max,5000},
              {tcp_listen_options,
                        [binary,
                          {packet, raw},
                          {reuseaddr, true},
                          {backlog, 128},
                          {nodelay, true},
                          {exit_on_close, false},
                          {keepalive, true}
                         ]
              },
              {collect_statistics_interval, 60000}
            ]
   },
   {rabbitmq_management_agent, [ {force_fine_statistics, true} ] },
   {kernel, [{net_ticktime,  30}]}
].""")

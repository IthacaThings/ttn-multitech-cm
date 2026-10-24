# sshhost

Setup of host used as target of SSH tunnels

## Requirements

Linux host on the Internet with ssh installed.

## Role Variables

- `sshhost_client_alive_interval` (default 15) and
  `sshhost_client_alive_count_max` (default 3) set sshd's
  `ClientAliveInterval` and `ClientAliveCountMax`.  sshd drops a tunnel
  whose gateway has stopped answering after about 45 seconds, so the
  gateway can connect again on its new network.  Without them, a dead
  session holds the tunnel's port for several minutes.

## Dependencies

None at this time

## Example Playbook

Add the following in site.yml to configure the ssh tunnel endpoint host

```yaml
- hosts: jumphost.example.com
  roles:
    - sshhost
```

## License

MIT

## Author Information

Jeffrey C Honig <jch@honig.net>

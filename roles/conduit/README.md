# CONDUIT

TTN setup for a Multi-Tech MultiConnect® Conduit™

## Requirements

The following setup must be set up performed on the Contduit:

- Install mLinux (this has not been tested on AEP)
- Configure Network
- Install a few packages for Ansible to run
- Install authorized keys
  - This is required to allow secure login to the gateway
  - These are maintained in `authorized_keys` or `authorized_keys_GROUP`
- Configure ssh tunnel
  - If accessing the Conduit remotely and it is not availble on the
    public Internet (and it should not be), an ssh tunnel needs to
    be configured.

## Role Variables

- **hostname**: The hostname of this node in the format
  *ttn-**ORG**-**NODE***
- **timezone**: The timezone for this node, i.e. a file path rooted at
  */usr/share/zoneinfo*.  E.g.: **US/Eastern**
- **region**: The region sets the frequency band, one of **AU**,
  **EU**, or **US**
- **router**: Sets the router to use, one of **switch-router**
  **ttn-router-asia-se** **ttn-router-brazil** **ttn-router-eu**
  **ttn-router-us-west**
- **contact_email**: An e-mail address to contact if there is a problem
  with the gateway
- **description**: Description of the gateway's location
- **ntp_servers**: A list of region appropriate NTP servers
  (i.e. 0,1,2.north-america.pool.ntp.org).  The first is used with
  ntpdate to set the hwclock and the others are used to keep the
  time in sync
- **latitude**, **longitude**: Co-ordinates of this gateway
- **altitude**: Altitude of this gateway in meters
- **ssh_tunnel_gateway_user_on_jumphost**: User configured on the
  tunnel server (for use by the gateway)
- **ssh_tunnel_ansible_user_on_jumphost**: User configured on the
  tunnel server (for use by ansible)
- **ssh_tunnel_remote_host**: Hostname or IP address of tunnel server
- **ssh_tunnel_ssh_key**: File name of ssh key to authenticate to the
  tunnel server
- **ssh_tunnel_ssh_port**: Port number to ssh into the tunnel server.
  Usually 22
- **ssh_tunnel_daemon**: Command to start an ssh tunnel, usually
  /usr/local/bin/ssh_tunnel
- **ssh_tunnel_remote_port**: Port on the tunnel server to use to
  contact this host.  Must be unique for each Conduit
- **use_cellular**: Use a cellular modem
- **cellular_apn**: Enable ppp and have it connect to this cellular APN
- **cellular_provider**: The cellular provider to use, defaults to
  *gsm*
- **cellular_send_interval**: The LoRA send interval when using
  cellular
- **cellular_keepalive_interval**: The LoRA keepalive interval when
  using cellular
- **mlinux_feed_suffix**: Appended to the mLinux version in the image
  and opkg feed URLs.  Defaults to **""**; **"-devel"** selects the
  test builds published by meta-ttni
- **conduit_package_upgrade**: Upgrade installed packages from the
  opkg feeds on every run, defaults to **true**.  Only the packages
  `opkg list-upgradable` reports are upgraded
- **conduit_package_upgrade_timeout**: Seconds the upgrade may run,
  defaults to **14400**.  It runs in the background and Ansible polls
  it every minute, so a dropped ssh connection doesn't fail it
- **conduit_package_hold**: Packages a package upgrade leaves alone,
  because the role installs them at a specific version.  Defaults to
  the mp, poly and ttn packet forwarders; *lora-basic-station* is
  added when **forwarder_variant** is **basic** and
  **forwarder_version** is set
- **conduit_package_conffiles**: What to do when an upgrade leaves the
  package's version of a changed conffile as *FILE-opkg*.  Maps
  *FILE* to **keep: package**, which installs the package's version
  and runs **command** if given, or **keep: local**, which removes
  *FILE-opkg*.  The play fails on any *FILE-opkg* not listed.  By
  default */etc/ca-certificates.conf* takes the package's version and
  rebuilds the CA bundle, and */var/config/lora/local_conf.json* keeps
  ours
- **conduit_monitor_network_ping_hosts**: IPv4 or IPv6 addresses that
  *monitor_network* pings.  Defaults to **[monit_ping_host]** if that
  is set, otherwise 8.8.8.8, 1.1.1.1 and 9.9.9.9
- **conduit_monitor_network_interval**: Seconds between rounds of
  checks, defaults to **30**
- **conduit_monitor_network_ttn_probe_interval**: Seconds between TLS
  probes of the TTN router, defaults to **600**
- **conduit_monitor_network_alert_after**: How long the next hop or
  the Internet can be unreachable before monit alerts, defaults to
  **3 minutes**
- **conduit_monitor_network_tunnel_alert_after**: The same for the ssh
  tunnel, defaults to **10 minutes**
- **conduit_monitor_network_ttn_alert_after**: The same for the
  connection to TTN, defaults to **5 minutes**.  This only alerts, so
  a TTN outage doesn't reboot every gateway at once
- **conduit_monitor_network_reboot_after**: How long the Internet can
  be unreachable before monit reboots, defaults to **45 minutes**
- **conduit_monit_reboot_command**: What monit runs to reboot.
  Defaults to */usr/local/lib/reboot_with_reason*, which records the
  reason and the last network status in
  */var/config/log/monitor_network.log* first

## Dependencies

None

## Example Playbook

Including an example of how to use your role (for instance, with
variables passed in as parameters) is always nice for users too:

```yaml
- hosts: conduits
  roles:
     - conduit
```

## Tags

The following tags can be used to run a subset of the playbook.

- **setup**: Initial Ansible setup, including setting up for custom
  facts
- **hostname**: Sets the Conduit's hostname
- **time**: Configures the timezone and syncs to time servers
- **users**: Adds the *ttn* user and sets ssh login keys
- **sshd**: Configures and secures sshd
- **services**: Config for other services, currently just disables
  mosquitto
- **localtree**: Moves */usr/local* tree to */var/config/local*
- **forwarder**: Removes the Multi-Tech packet forwarder and installs
  the TTN Poly Packet Forwarder
- **loraconfig**: Registers gateway and sets up */var/config/lora* and
  the necessary config files
- **ssh_tunnel**: Sets up an ssh tunnel back to a control host
- **monitor_network**: Installs *monitor_network* (also run by the
  **monit** and **conduit_leds** tags)
- **monitor_modem**: Installs *monitor_modem* on gateways with a
  cellular modem
- **mlinux**: Configures the opkg feeds and upgrades mLinux to
  **mlinux_version**
- **packages**: Upgrades installed packages from the opkg feeds (see
  **conduit_package_upgrade**)

## Network monitoring

*monitor_network* runs on every gateway.  Every 30 seconds it checks
the next hop, pings the **conduit_monitor_network_ping_hosts**,
resolves the TTN router and the jump host, and looks for an
established ssh tunnel and connection to TTN.  It does not rely on
ping alone, since some sites drop ICMP.  Each check that succeeds
touches a file in */run/monitor_network*, and monit only looks at the
ages of those files:

| File          | monit action                                         |
|---------------|------------------------------------------------------|
| *nexthop.ok*  | Alert                                                |
| *internet.ok* | Alert, then reboot after **45 minutes**              |
| *tunnel.ok*   | Alert (only when the ssh tunnel is enabled)          |
| *ttn.ok*      | Alert                                                |

The latest results and a diagnosis are in
*/run/monitor_network/status*.  Changes, and the reason for each
reboot, are logged to */var/config/log/monitor_network.log*, which is
kept across reboots.

On gateways with a cellular modem, *monitor_modem* switches to PPP
when the wired or WiFi link stops answering pings for 3 cycles in a
row, and retries that link after 10 minutes, doubling the wait each
time the retry fails, up to 3 hours.  It starts and stops pppd itself;
monit only watches *ppp0*.  It looks up its ping target once per
cycle and keeps using the last address it found, so a DNS failure
doesn't look like a dead link.  When pppd is not running it puts back
the */var/run/resolv.conf* that ppp's ip-up script saved, if ppp's
ip-down script did not.

## LED Status

On Conduits (not Conduit APs), *monitor_network* sets the LEDs:

| LED    | Meaning                                                      |
|--------|--------------------------------------------------------------|
| Status | Blinks twice a second when the OS is running                 |
| LS     | Blicks every couple seconds when Cellular modem is connected |
| A      | We are trying to use PPP                                     |
| B      | An SSH tunnel connection to the jump host is Established     |
| C      | A packet forwarder is running and has the LoRa device open   |
|        | (does not work on I2C cards running mp)                      |
| D      | DNS resolution of the TTN router works                       |

The A-D LEDs are the ones on the right and have different lables on
older Conduits (CD and one to 3 bars).

The A-D LEDs reverse periodically to indicate that the check program
is running.

## License

MIT

## Author Information

Jeffrey Honig <jch@honig.net>

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
- **untrusted_ca_certificates**: A list of CA certificates, as named in
  */etc/ca-certificates.conf* (e.g.
  **mozilla/emSign_ECC_Root_CA_-_G3.crt**), to distrust in the system
  certificate store.  Only entries already present are modified.  Set
  to **[]** to disable.

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
- **security-fixes**: Applies fixes for security issues not yet
  addressed by mLinux, such as distrusting compromised CA certificates
- **services**: Config for other services, currently just disables
  mosquitto
- **localtree**: Moves */usr/local* tree to */var/config/local*
- **forwarder**: Removes the Multi-Tech packet forwarder and installs
  the TTN Poly Packet Forwarder
- **loraconfig**: Registers gateway and sets up */var/config/lora* and
  the necessary config files
- **ssh_tunnel**: Sets up an ssh tunnel back to a control host

## LED Status

On Conduits (not Conduit APs), the LED indications are:

| LED    | Meaning                                                      |
|--------|--------------------------------------------------------------|
| Status | Blinks twice a second when the OS is running                 |
| LS     | Blicks every couple seconds when Cellular modem is connected |
| A      | We are trying to use PPP                                     |
| B      | An SSH tunnel connection to the jump host is Established     |
| C      | A packet forwarder is running and has the LoRa device open   |
|        | (does not work on I2C cards running mp)                      |
| D      | DNS resolution of google.com works                           |

The A-D LEDs are the ones on the right and have different lables on
older Conduits (CD and one to 3 bars).

The A-D LEDs reverse periodically to indicate that the check program
is running.

## License

MIT

## Author Information

Jeffrey Honig <jch@honig.net>

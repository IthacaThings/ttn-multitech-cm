# Configuration Management for Multi-Tech Conduits as The Things Network Gateways

This repo is a bunch of Ansible playbooks and configuration used to
manage a group of Multi-Tech Conduits as Things Network gateways in an
a Things Network Org.

## Proposed Configuration Workflow
### Manual setup
This manual setup would be performed to get the gateway on the
network.  Can be performed in the "factory".
+ Configure DHCP or Address/Netmask/Gateway/DNS
+ Install Packages necessary packages
    + opkg update
	+ opkg install python-pkgutils
	+ opkg install python-distutils
+ Set up SSH tunnel back to server unless on public network
+ Install an ssh key for root access
### One-time Ansible setup
This is performed one-time to setup secure networking and is basically
repeating above configuration from master config.  Must be performed
on-site with access to the gateay
+ SSH tunnel
+ Login access (ttn account with root access)
### Standard Ansible setup
#### Login access
This secures the box by not having a known account (root) and
restricting root access.
+ ttn or ttn-ORG account (i.e. ttn-ith)
+ Unique access
+ Install SSH keys
#### SSH config
+ Disable password login
+ Require Keys
### [X] Install Let's Encrypt Root Certificates
+ This will avoid the need for --no-check-certificate on wget
### [X] Set hostname
This makes it obvious which gateway you are logged in to.
+ ttn-ORG-NAME (where NAME is descriptive)
### [X] Set timezone
An org is usually all in one timezone so it's just easier to configure
this globally.  Ansible will spit out error messages if you get it wrong.
+ Manually configured via Ansible vars
### [X] Set time
The current config only seems to use *ntpdate* once at setup.  It's
better if the gateway uses *ntpd* or does a periodic *ntpdate*.

NTP server pool to use should be configured globally.

### Disable Multi-Tech Lora daemon
Uninstall lora-network-server with opkg
### Install TTN packet forwarder
Install the local copy of TTN packet fowarder and config files.

Config files will be stored in this repo and the merged file for the
Gateway will be generated on the device where Ansible is run.

The check for updated config files will be removed from the startup
script.

Restart daemon when done.

## Reference

### How to
#### Fetch the latested upstream files
+ Run ```make```
+ Test
+ Commit

### Ansible directory tree
+ ansible.cfg - General ansible config
+ hosts - lists of ansible hosts in groups
+ group_vars - group specific vars
    + all.yml - Global vars
    + *GROUP*.yml - Grooup specific vars
+ host_vars - host specific vars
    + *HOST*.yml - Host specific vars
+ roles - Local roles
+ galaxy-roles - Downloaded roles

### Ansible Variables
+ hostname - ttn-region-location
+ timezone - File rooted at /usr/share/zoneinfo
+ region
	+ frequency - EU868, AU915, US915
	+ ntp servers - by region?
+ latitude
+ longitude
+ altitude
+ contact_email
+ description - description of location (contact phone?)

## Questions
+ Do we set a password for root/ttn or just allow key-based login?
    + Or do we only allow password login on the console?

## Issues
+ su does not work with busybox so we need to ssh in as root
+ wget still needs --ca-certificate=/etc/ssl/certs/ca-certificates.crt


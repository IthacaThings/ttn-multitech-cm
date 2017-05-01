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
+ [X] ttn account
+ [X] Install SSH keys for root and ttn
+ [ ] Disable password login?
+ [ ] Set root and ttn passwords?
#### SSH config
+ [ ] Disable password login
    + Needs discussion
+ [X] Require Keys for root login
### Install Let's Encrypt Root Certificates
+ This will avoid the need for --no-check-certificate on wget
### Set hostname
This makes it obvious which gateway you are logged in to.
+ ttn-ORG-NAME (where NAME is descriptive)
### Set timezone
+ [X] - Set from Ansible config
An org is usually all in one timezone so it's just easier to configure
this globally.  Ansible will spit out error messages if you get it wrong.
### Set time
+ [X] Set time when Ansible is run
+ [ ] Set time periodically
   + Cron script?
   + NTPD?
### Disable Multi-Tech Lora daemon
+ [X] Uninstall lora-network-server with opkg
### Install TTN packet forwarder
+ [X] Fetch ipkg of ttn packet forwarder
+ [X] Install package
+ [ ] Overwrite init.d file to not fetch updates
+ [X] Fetch global config files
+ [X] Install appropriate config file
+ [X] Generate local config file
+ [ ] Merge overrides
+ [ ] Restart daemon when done

### Registration
+ [ ] Fetch the correct version of [ttnctl](https://www.thethingsnetwork.org/docs/network/cli/quick-start.html#device-management)
+ [ ] Register gateway with TTN
+ [ ] Figure out how to handle credentials

## Reference

### Initial setup of this repo
+ Clone this repo into your own GitHub org or account
+ Install [ansible](XXX) on your system
+ Run ```make``` to fetch the required upstream files
+ Modify *group_vars/all.yml* for your global config items
+ Add each of your gateways to *hosts*
+ Add a file for each of your hosts in *host_vars/**HOST**.yml*
+ XXX - Syntax check
+ XXX - Ping host
+ XXX - Apply

### Deploying a Conduit
+ Configure host specific data in this control repo
+ Configure the conduit on the local network
+ Set a secure root password
+ Copy *roles/common/files/authorized_keys* to */home/root/.ssh/*
+ Run the following commands so Ansible can run
```
# opkg update
# opkg install python-pkgutils
# opkg install python-distutils
```
+ Setup a secure tunnel if the Ansible machine is not on the same network
+ Test ansible
```
$ ansible HOSTNAME -m ping
```
+ Run Ansible
```
ansible-playbook -l HOSTNAME site.yaml
```
+ Register the gateway
XXX

### Syncing changes to the latest upstream files
You'll want to do this if the global configurations change, or if
there is a new version of the poly-packet-forwarder.  The same testing
steps apply if there is a new version of mLinux.

#### Commit all your changes
Before upgrading to new upstream files you should at least commit all
your changes.  You could also create a new branch to work on
#### Fetch the files
```$ make```
#### Test the changes
Deploy the changes to a Conduit you use for testing.  Verify that
everything works.  Deploy to another Conduit or two to make sure.
#### Commit your changes
Commit your changes to your git repo.
#### Deploy
Deploy your changes to all your Conduits, verify.
#### Commit again
If you were working on another branch, push your changes to *master*

### Ansible directory tree
+ ansible.cfg - General ansible config
+ hosts - lists of ansible hosts in groups
+ group_vars - group specific vars
    + all.yml - Global vars
    + *GROUP*.yml - Group specific vars
+ host_vars - host specific vars
    + *HOST*.yml - Host specific vars
+ roles - Local roles
+ galaxy-roles - Downloaded roles

### Ansible Variables
Variables can be defined at three levels:
+ Globally (define in **group_vars/all.yml**)
+ Per group if you use them (define in **group_vars/GROUP.yml**)
+ Per host (define in **host_vars/HOST.yml**)

The available variables are defined in the [common role README](roles/common/README.md).

## Questions
+ Do we set a password for root/ttn or just allow key-based login?
    + Or do we only allow password login on the console?

## Issues
+ su does not work with busybox so we need to ssh in as root
+ wget still needs --ca-certificate=/etc/ssl/certs/ca-certificates.crt


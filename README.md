[appurl]: http://www.thethingsnetwork.org/
[![The Things Network](https://ttnstaticfile.blob.core.windows.net/static/ttn/media/logo/TheThingsRond.png)][appurl]

# Configuration Management of Multi-Tech Conduits as The Things Network Gateways

This repo contains Ansible playbooks and configuration used to manage
a group of Multi-Tech Conduits
as [Things Network gateways](http://www.thethingsnetwork.org) in an a
Things Network
organization.
The [MultiConnect® Conduit™](http://www.multitech.com/brands/multiconnect-conduit) is
one of the more popular [LoRa®](http://lora.multitech.com/) Gateways
is use.

# Table of Contents
1. [Initial Setup](#initial-setup)
2. [Deploying a Conduit](#deploying-a-conduit)
3. [Syncing with Upstream](#syncing-with-upstream)
4. [Reference](#reference)
5. [Development](#development)

# Initial setup
Before you start you need to make a copy of this git repo and
configure it for your TTN organization.

## Fork this repo into your own Github account

XXX 

##  Install Anisble
The machine on which you run Ansible is called the *Control Machine*.
This setup has been tested on macOS (with Home Brew), Linux and under
Windows Subsystem for Linux using Ansible 2.2.

Instructions for installing Ansible
[can be found here](https://docs.ansible.com/ansible/intro_installation.html).

## Fetch the upstream files

There is *Makefile* in the root of this repo that can be used to fetch
files from upstream.  These include the *Poly Packet Forwarder*
package, global configuration files and the *Let's Encrypt* signing
certificate.

### make fetch
There are two commands to relating to fetching upstream files.  This
command will fetch files that are required, but updates can
potentially break gateway configuration.  After an initial deploy,
these updated files should be used in a test environment to ensure
that nothing breaks before deploying them to a production environment.

Before your initial configuration, run this command.

```
$ make fetch
```

### make all
Files that are required to run, or are built from data obtained from
Gateways will be downloaded everytime *make* is run with *all* or no
argument.

```
$ make all
```

## Set Global variables
Modify *group_vars/conduits.yml* for your global config items.  The default
framework assumes that all gateways are in the same region and
timezone.

## Add each of your gateways to *hosts*
Normally you would put them in the *production* group.  There is also
a *test* group.

You can divide them into other groups, such as different areas of
your organizations region.  See Ansible documentation
on [inventory](https://docs.ansible.com/ansible/intro_inventory.html)
for more information.

## Add a file for each of your hosts in *host_vars/**HOST**.yml*
Most of these variables should be self-explanitory.

## Run a syntax check
```
$ make TARGET=*HOSTNAME* syntax-check
```

## See if you can talk to the host
```
$ make TARGET=*HOSTNAME* ping
```

## Apply the playbook to the host
```
$ make TARGET=*HOSTNAME* apply
```

# Deploying a Conduit
## Configure host specific data in this control repo
## Configure the conduit on the local network
## Set a secure root password
## Copy *roles/common/files/authorized_keys* to */home/root/.ssh/*
## Run the following commands so Ansible can run
```
# opkg update
# opkg install python-pkgutils
# opkg install python-distutils
```
## Setup a secure tunnel if the Ansible machine is not on the same network
## Test ansible
```
$ ansible HOSTNAME -m ping
```
## Run Ansible
```
$ ansible-playbook -l HOSTNAME site.yaml
```
## Register the gateway
Registration happens automatically in the list step of applying the
playbook.  For this to happen, you need to be logged in.  To do this you need to log into [The Things Network](https://www.thethingsnetwork.org) and then click [this link](https://account.thethingsnetwork.org/users/authorize?client_id=ttnctl&redirect_uri=/oauth/callback/ttnctl&response_type=code) to generate a *TOKEN*.  Then log in using:
```
$ bin/ttnctl user login *TOKEN*
```

To manually re-run the registration step:

```
$ make apply TAGS=register TARGET=*HOSTNAME*
```
Specify the name of your Conduit with *HOSTNAME*.  If you leave that
off, all Conduit's will be registered, or their registration will be
updated. 

# Syncing with Upstream
This is necessary when the global configurations change, or if there
is a new version of the poly-packet-forwarder.  The same testing steps
apply if there is a new version of mLinux.

## Commit all your changes
Before upgrading to new upstream files you should at least commit all
your changes.  The best practice would be to create a new branch for
this testing.
### Fetch the files
```
$ make
```
You can see what, if anything changed with git:
```
$ git status
```
## Test the changes
Deploy the changes to a Conduit you use for testing.  Verify that
everything works.  Deploy to another Conduit or two to make sure.
## Commit your changes
Commit your changes to your git repo.
## Deploy
Deploy your changes to all your Conduits, verify.
## Commit again
If you were working on another branch, push your changes to *master*

# Reference

## Ansible directory tree
+ ansible.cfg - General ansible config
+ hosts - lists of ansible hosts in groups
+ group_vars - group specific vars
    + conduits.yml - Vars for all conduits
    + *GROUP*.yml - Group specific vars
+ host_vars - host specific vars
    + *HOST*.yml - Host specific vars
+ roles - Local roles
+ galaxy-roles - Downloaded roles

## Ansible Variables
Variables can be defined at three levels:
+ Globally (define in **group_vars/conduits.yml**)
+ Per group if you use them (define in **group_vars/GROUP.yml**)
+ Per host (define in **host_vars/HOST.yml**)

The available variables are defined in the [common role README](roles/common/README.md).

---

# Development 

This is a temporary section to track development on this repo.

## Issues
Things to do before this repo is ready to release to the world.

+ su does not work with busybox so we need to ssh in as root
+ wget still needs --ca-certificate=/etc/ssl/certs/ca-certificates.crt
+ Do we set a password for root/ttn or just allow key-based login?
    + Or do we only allow password login on the console?


## TODO

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
+ [X] Configure and start ntpd
### Disable Multi-Tech Lora daemon
+ [X] Uninstall lora-network-server with opkg
### Install TTN packet forwarder
+ [X] Fetch ipkg of ttn packet forwarder
+ [X] Install package
+ [X] Avoid install step if already installed
+ [X] Overwrite init.d file to not fetch updates
+ [X] Fetch global config files
+ [X] Install appropriate config file
+ [X] Generate local config file
+ [X] Merge overrides
+ [X] Restart daemon when done

### SSH Tunnel
+ [X] Write init.d script
+ [X] Set parameters in /etc/defaults/XXXX (host, id, port)
+ [X] Script to keep ssh running
+ [X] Use system /etc/ssh/ssh_host_rsa_key?  Tells if the system has been updated
+ [X] Generate authorized_keys scripts for tunnel server
+ [ ] Generate ufw configs
+ [ ] Generate .ssh/config with node names
+ [ ] Document sudo password

### Registration
+ [X] Fetch the correct version of [ttnctl](https://www.thethingsnetwork.org/docs/network/cli/quick-start.html#device-management)
+ [X] Register gateway with TTN

### Firmware updates
Can we deploy a new version of Multi-Tech mLinux remotely without
needing to be hands on with the gateways?
+ [ ] Does /var/config survive firmware updates
    + [ ] Move root and ttn users home dirs to /var/config
	+ [ ] Test remote updates
	+ [ ] Add /etc/init.d service to install Ansible dependencies

### Setup
#### Makefile targets to
+ [ ] Add a host
    + [ ] Validate hostname (ttn-ORG-NAME)
	+ [ ] Prompt for config variables or just edit?
	+ [ ] Which group to add to?  Allow config parameter?
+ [ ] Add a host with a tunnel
+ [X] Collect facts (anisible -m setup)
+ [X] Ping hosts
+ [X] Syntax check


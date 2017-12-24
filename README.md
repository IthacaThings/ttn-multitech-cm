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

# About this Repo

## Key based authentication

Using passwords over the Internet is not secure. This control repo is
set up to rely on ssh keys. It is assumed that you know how to
generate an ssh key and how to provide your key for remote
authentication. It is also recommended that you use ssh-agent to
forward keys from your local system to the jump host and not keep
private keys on cloud hosts.

## Jump Host

This configuration relies on a *jump host* or ssh tunnel host. For
various reasons, including security and the complexity of traversing
firewalls, each conduit will set up a reverse SSH tunnel to a jump
host. 

It is recommended that these ports only be accessible from that jump
host. That will mean you need to be logged into the jump host to run
the Ansible configuration and to ssh into the conduits.

To ssh into a specific conduit, find it's *ssh_tunnel_remote_port* and
issue the following command on the jump host.

```
$ ssh -P PORT root@localhost
```

If you do not want to use a jump host, comment out
*ssh_tunnel_remote_port* or set it to *0* in your conduit's config
file in *host_vars*.

## Branches 

This repo has a few main branches:

### master

This is the repo to clone to generate a configuration for your local
org.  If you rebase to the latest version of this branch you will get
all the latest features.

### ttn-ithaca

This is the branch we use for the configuration for TTN Ithaca.  This
branch will periodically be rebased to master to keep the Ithaca
configuration in sync.

### Othar branches

These will be for development and may be move back to master,
discarded, or left to rot.  Use at your own risk.

# Initial setup
Before you start you need to make a copy of this git repo and
configure it for your TTN organization.

## Clone the master branch

I'm not going to put a git/Github tutorial in here, just some advice.

If you are using the TTN-Ithaca ttn-multitech-cm repo you'll want to
create a new branch.  If you are using your own repo you can Fork
*master* or set it as your upstream.

Remember to create a branch and submit a pull request for changes you
want considered for *master*.

##  Install Anisble
The machine on which you run Ansible is called the *Control Machine*.
This setup has been tested on macOS (with Home Brew), Linux and under
Windows Subsystem for Linux using Ansible 2.2.

Instructions for installing Ansible
[can be found here](https://docs.ansible.com/ansible/intro_installation.html).

## Fetch the upstream files

There is *Makefile* in the root of this repo that can be used to fetch
files from upstream.  

### make all
This command will fetch files that are required to run ansible on the
target.  Principly the ttnctl binary needed to register a gateway with
TTN.

Updates can potentially break gateway configuration.  After an initial
deploy, these updated files should be used in a test environment to
ensure that nothing breaks before deploying them to a production
environment.

Before your initial configuration, run this command.

```
$ make all
```

## Set up initial files

### Set Global variables
Copy *group_vars/conduits-example.yml* to *group_vars/conduits.yaml*
and configure your global config items.  The default framework assumes
that all gateways are in the same region and timezone.

### Start an inventory
Copy *hosts-example* to *hosts*

### Set authorized keys for logging into conduits
Edit the *authorized_keys* variable in the group configuration for
your conduits (i.e. *group_vars/conduits.yml*) *AND* the jumphost
configuration (*host_vars/jumphost.example.com/yml*) to provide a list
of ssh public keys that can have access to your conduits and jumphost.
As mentioned above, it's recommended that you use ssh-agent and
forward keys from your laptop or desktop.

### Add an ssh tunnel server (i.e. jump host)
1. Edit *hosts* and change *jumphost.example.com* to the FQDN of your
ssh tunnel server, aka jumphost.
2. Copy *group_vars/jumphost.example.com* to
*group_vars/FQDN_OF_YOUR_JUMPHOST.yam* and edit it as necessary.

## Add each of your gateways to *hosts*
Normally you would put them in the *production* group.  There is also
a *test* group that you can use if you have one or more gateways you
use for testing.

You can divide them into other groups, such as different areas of
your organizations region.  See Ansible documentation
on [inventory](https://docs.ansible.com/ansible/intro_inventory.html)
for more information.

## Add a file for each of your hosts in *host_vars/**HOST**.yml*
Copy *host_vars/ttn-org-example.yml* for each of your nodes.  Remember
that *ttn-* is constant, *org* should be the name of your TTN
organization and *example* will be a name for this conduit.  Use a
short descriptive name.  I.e. ttn-nyc-midtown or ttn-ith-coopext.

Most of the variables in this file should be self-explanitory.

*NOTE*: that you will need to keep track of the *ssh_tunnel_remote_port*
values on each of your conduits to make sure they are unique.

## Run a syntax check
```
$ make TARGET=*HOSTNAME* syntax-check
```

## See if you can talk to the host
```
$ make TARGET=*HOSTNAME* ping
```
If ssh keys are not yet setup on the Conduit (i.e., if you've not done the first part of "Deploying a Conduit") this will fail.

## Apply the playbook to the host
```
$ make TARGET=*HOSTNAME* apply
```

# Deploying a Conduit
## Configure host specific data in this control repo
## Configure the conduit on the local network
By default a conduit will come up requesting a DHCP address on the
local network.  DHCP should also supply one or more nameservers.

You can override this in *host_vars/**HOST**.yml* by uncommenting and
setting the appropriate variable definitions.  See the examples in
*host_vars/ttn-org-example.yml*. 

Note that if you make a mistake you may render your Conduit
unreachable except via the USB serial console.  So double check the
values you set.

Also note that changing an interface to/from DHCP will require a
manual reboot of the Conduit after applying the Ansible
configuration.

###

It is also possible to support WiFi on the conduit with USB devices
that have the RealTek 8192cu chip, such as the Edimax EW-7811U.  It
may be possible to support other devices if you send one to our
developers.

With mLinux 3.3 we've tried the official Raspberry Pi adapter and the
Edimax combination Bluetooth/WiFi adapter without success.  A newer
kernel is required to support those devices.

## Set a secure root password
Ansible uses ssh keys to access the Conduit for configuation.  But it
is very important that you change the root password (which by default
is `root`).  This will keep someone from logging in and changing your
configuration, or turning your Conduit into a BotNet node.

On the Conduit:
```
mtctd login: root
passwd: 
root@mtcdt:~# passwd
Enter new UNIX password:
Retype new UNIX password:
root@mtcdt:~#
```
Remember the password you supplied above.  

## Provide initial authorizied keys in .root/.ssh/authorized_keys
The easy way to do this is to open *authorized_keys* with `gedit` on your host, then copy/paste
to a terminal window.

## Run the following commands so Ansible can run
```
# opkg update
# opkg install python-pkgutil
# opkg install python-distutils
```
## Setup a secure tunnel if the Ansible machine is not on the same network
## Test ansible
```
$ ansible HOSTNAME -m ping
```
## Run Ansible
```
$ ansible-playbook -l HOSTNAME site.yml
```
## Register the gateway
Registration happens automatically during configuration of the router.  For this to happen, you need to be logged in.  To do this you need to log into [The Things Network](https://www.thethingsnetwork.org) and then click [this link](https://account.thethingsnetwork.org/users/authorize?client_id=ttnctl&redirect_uri=/oauth/callback/ttnctl&response_type=code) to generate a *TOKEN*.  Then log in using:
```
$ bin/ttnctl user login *TOKEN*
```

To manually re-run the registration step:

```
$ make apply TAGS=loraconfig TARGET=*HOSTNAME*
```
Specify the name of your Conduit with *HOSTNAME*.  If you leave that
off, all Conduit's will be registered, or their registration will be
updated. 

# Upgrading mLinux
It is possible to remotely upgrade to a specific version of mLinux
using this control repo.  This should be used with caution because if
an upgrade goes wrong you may leave your Conduit in a state that
requires manual intervention to restore it.

An upgrade requires lots of space on `/var/volatile` and will fail if
a lot of space is used by log files.  The best way to clear out the
space is to reboot, or stop the packet forwarder and delete the log
file.

Note that you will lose anything you have manually installed outside
of this control repo, except for files in /usr/local.  That includes
the home directories for root and the 'ttn' user defined by this repo.

To force a Conduit to mLinux 3.3.7, in *host_vars/**HOST**.yml* set:

```
mlinux_version: 3.3.7
```

and run

```make apply```

# Syncing with Upstream
This is necessary when the global configurations change, or if there
is a new version of one of the packet forwarder applications.  The
same testing steps apply if there is a new version of mLinux.

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

The available variables are defined in the [conduit role README](roles/conduit/README.md).

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

### Bugs and issues
+ [ ] Use /usr/sbin/mlinux-firmware-update as it checks validity and integrity
+ [ ] Break out ansible setup into ansible.yml
+ [ ] Break out other setup
+ [ ] Do not try to set hostname if it is not defined

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

### SSH Tunnel
+ [X] Write init.d script
+ [X] Set parameters in /etc/defaults/XXXX (host, id, port)
+ [X] Script to keep ssh running
+ [X] Use system /etc/ssh/ssh_host_rsa_key?  Tells if the system has been updated
+ [X] Generate authorized_keys scripts for tunnel server
+ [X] Generate ufw configs (NOT NECESSARY)
+ [ ] Generate .ssh/config with node names on jump host
+ [ ] Document sudo password
+ [X] Use autossh
+ [ ] Manage tunnel ports

### Setup
#### Makefile targets to
+ [ ] Add a host
    + [ ] Validate hostname (ttn-ORG-NAME)
	+ [ ] Assign tunnel port
	+ [ ] Prompt for config variables or just edit?
	+ [ ] Which group to add to?  Allow config parameter?
+ [ ] Add a host with a tunnel
+ [X] Collect facts (anisible -m setup)
+ [X] Ping hosts
+ [X] Syntax check


### Conduit/AP bootstrap
#### Phase I
+ [ ] Configure for DHCP
#### Phase II
+ [ ] Verify mlinux
+ [ ] Create ~root/.ssh (700)
+ [ ] Set authorized keys
+ [ ] 'PasswordAuthentication no' /etc/sshd_config
+ [ ] Configure ssh tunnel
    + [ ] /etc/init.d/ssh_tunnel
    + [ ] Jumphost
	+ [ ] Port
	+ [ ] Username
	+ [ ] /etc/default/ssh_tunnel
	+ [ ] /etc/init.d/ssh_tunnel restart
+ [ ] Fix /etc/opkg/mlinux-feed.conf (3.3 -> 3.3.X)
+ [ ] Install Ansible dependencies
    + [ ] opkg update || _error "opkg update failed"
    + [ ] opkg install python-pkgutil python-distutils || _error "opkg installed"

### Data to provide to Conduit
+ [ ] authorizied keys
+ [ ] Jump Host info
    + [ ] Address/IP
    + [ ] Port number
    + [ ] Username
### Data get from conduit
+ [ ] authorized key
+ [ ] MAC address

### DHCP fixes
+ [X] udhcpc_opts -t (86400*30) -b
+ [X] dhcp script to restart packet forwarder on DHCP up
+ [X] dhcp script to restart auto ssh on dhcp up?

### Bugs
+ [ ] Not owner of gateway


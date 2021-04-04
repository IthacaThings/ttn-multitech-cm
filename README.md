[appurl]: http://www.thethingsnetwork.org/
[![The Things Network](https://www.thethingsnetwork.org/spa/public/favicons/favicon-32.png)][appurl]

# Configuration Management of MultiTech Conduits as The Things Network Gateways

This repo contains Ansible playbooks and configuration used to manage
a group of [MultiTech MultiConnect®
Conduit™](http://www.multitech.com/brands/multiconnect-conduit) and
[MultiConnect® Conduit™ AP](https://www.multitech.com/brands/multiconnect-conduit-ap) gatewys
as part of a [Things Network](http://www.thethingsnetwork.org) [Community](https://www.thethingsnetwork.org/community).

The
[MultiConnect® Conduit™](https://www.multitech.com/products/gateways-routers-modems)
gateways are one of the more popular
[LoRa®](http://lora.multitech.com/) gateways is use.

# Table of Contents
1. [About this Repo](#about-this-repo)
1. [Initial Setup](#initial-setup)
1. [Deploying a Conduit](#deploying-a-conduit)
1. [Syncing with Upstream](#syncing-with-upstream)
1. [Support](#support)
1. [Reference](#reference)

# About this Repo

## Ansible

Ansible works by changing the state of the target system. This
includes updating configuration files. If manual changes are made to
these files those changes may be overwritten when running
Ansilble. It's best to expand the Ansible control repo to support the
changes you need instead of making local changes.

## mLinux version

This repo has been extensively tested on later versions of mLinux
3.3.  It is recommended to update conduits to a later version of
mLinux before running this repo. It is important to keep your version
of mLinux up to date to keep up with any security fixes.

All of the Multitech images require additional packages installed
manually to work with this repo. For that reason We recommend our
[custom build of
mLinux](https://github.com/IthacaThings/mlinux-images) which has been
optimized for use with The Things Network. This version has tools to
preserve configutation during mLinux firmware updates.  In addition
necessary packages have been pre-installed on this version and
unnecessary packages have been removed.  Instructions are on the above
page.

You can find Multitech versions of mLinux on the [image
downloads](http://www.multitech.net/mlinux/images/)page. Be sure to
select the correct version for your Conduit (mtcdt) or Conduit AP
(mtcap). MultiTech has
[instructions](http://www.multitech.net/developer/software/mlinux/using-mlinux/flashing-mlinux-firmware-for-conduit/)
for installing mLinux.

*NOTE*: When not using our version of mLinux, most configuration is
not perserved when doing an mLinux firmware, so make sure you have
configured Ansible with any configuration.

### Preserving configuration during an mlinux upgrade

The TTNI custom build of mLinux includes a tool to preserve
configuration during an mLinux firmware upgrade. This tool will
eventually be installed on any version of mLinux 3.3 configured via
this Ansible configuration.

Ansible Preserves configuration by ensuring all local changes that
must be preserved are stored in the /var/config filesystem with
symlinks from filesystems that are not preserved. The contents of this
filesystem is normally preserved during a firmware upgrade. In
addition a script runs before a firmware upgrade and saves a list of
symlinks into /var/config. These symlinks are restored on the first
boot after a firmware upgrade.

Packages installed in /opt (such as the Kersing packet forwarder) are
not preserved and are re-installed by Ansible after a firmware
upgrade. 

## Key based authentication

Using passwords over the Internet is not secure. This control repo is
set up to rely on ssh keys. It is assumed that you know how to
generate an ssh key and how to provide your key for remote
authentication. It is also recommended that you use ssh-agent to
forward keys from your local system to the jump host and not keep
private keys on cloud hosts.

## Commissioning

From version 5.2, official mLinux images require commisioning to
create login creditionalls before an initial logging into the
conduit.

The script
`bin/commission` is intented to perform this function.

Run it as

```bash
bin/commission --address 192.168.2.1 --password PASSWORD
```

This will set the password for the `mtadm` user (or specify a user
with `--username USER` so that you can log in and do initial setup.

## Jump Host

This configuration relies on a *jump host* or ssh tunnel host. For
various reasons, including security and the complexity of traversing
firewalls, each Conduit will set up a reverse SSH tunnel to a jump
host. 

It is recommended that these ports only be accessible from that jump
host. That will mean you need to be logged into the jump host to run
the Ansible configuration and to ssh into the Conduits.

To ssh into a specific Conduit, find it's *ssh_tunnel_remote_port* and
issue the following command on the jump host.

```
$ ssh -P PORT root@localhost
```

If you do not want to use a jump host, comment out
*ssh_tunnel_remote_port* or set it to *0* in your Conduit's config
file in *host_vars*.

## Branches 

This repo has a few main branches:

### master

This is the repo to clone to generate a configuration for your local
org.  If you rebase to the latest version of this branch you will get
all the latest features.

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
Copy *group_vars/conduits-example.yml* to *group_vars/conduits.yal*
and configure your global config items.  The default framework assumes
that all gateways are in the same region and timezone.

### Start an inventory
Copy *hosts-example* to *hosts*

### Set authorized keys for logging into Conduits
Edit the *authorized_keys* variable in the group configuration for
your Conduits (i.e. *group_vars/conduits.yml*) *AND* the jumphost
configuration (*host_vars/jumphost.example.com/yml*) to provide a list
of ssh public keys that can have access to your Conduits and jumphost.
As mentioned above, it's recommended that you use ssh-agent and
forward keys from your laptop or desktop.

### Add an ssh tunnel server (i.e. jump host)
1. Edit *hosts* and change *jumphost.example.com* to the FQDN of your
ssh tunnel server, aka jumphost.
2. Copy *group_vars/jumphost.example.com* to
*group_vars/FQDN_OF_YOUR_JUMPHOST.yml* and edit it as necessary.

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
organization and *example* will be a name for this Conduit.  Use a
short descriptive name.  I.e. ttn-nyc-midtown or ttn-ith-coopext.

Most of the variables in this file should be self-explanitory.

*NOTE*: that you will need to keep track of the *ssh_tunnel_remote_port*
values on each of your Conduits to make sure they are unique.

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
## Configure the Conduit on the local network
By default a Conduit will come up requesting a DHCP address on the
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

It is also possible to support WiFi on the Conduit with USB devices
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

## Run the following commands to install pre-requisites for Ansible
### Conduit with mLinux factory image
```
# opkg update
# opkg install python-pkgutil install python-distutils
```
### Conduit or Conduit AP with mLinux base image
```
# opkg update
# opkg install python-async python-argparse python-compression python-dateutil python-html python-psutil python-pycurl python-pyopenssl python-pyserial python-pyudev python-pyusb python-simplejson python-syslog python-textutils python-unixadmin python-xml python-distutils python-json python-pkgutil python-shell
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

# Support

This repo is a volunteer effort and as such there is no support.  It
is primarily developed in support of TTN Ithaca and TTN NYC.  We are
happy to see it used by other TTN communities.

There is a channel for discussion of this repo at [The Things Network
Community SLACK](https://thethingsnetwork.slack.com/messages/CBKCZP09J).

# Reference

## Makefile reference

The configuration files/directories can be located outside if this
repo if you create a link named *.ttn_org* or set the TTN_ORG Makefile
or environment variable.

### Makefile command line variables

#### TAGS

A comma separated list of tags.  Used to limit what parts of the
configuration are applied

#### TARGET

A comma separated list of targets, could be *conduit* for all
conduits, or individual hostnames.

#### OPTIONS

Additional *ansible-playbook* arguments

#### TTN_ORG

If this is defined it points to a directory from which to obtain the
*hosts* (or *inventory*) and *catalog* directories.  This allows this
repo to be used with an external configuration.

### Makefile targets

#### apply

Apply the configuration to the specified targets

#### apply-debug

Apply the configuration with full debugging

#### test

Run the rules in test mode. Some rules may fail due to dependencies.

#### test-debug

Test the config with full debugging

#### syntax-check

Run a syntax-check on the configuration

#### ping

Check reachability of all the targets

#### list-hosts

Output a list of all the hosts defiled in *hosts* or *inventory*

#### list-tags

List the tags available

#### retry

Retry the hosts that failed as specified in @site.retry

#### ansible-setup

Ensure all packages that Ansible requires to run are installed.

Ensure that ANSIBLE_DEPENDS in the Makfile matches
roles/conduit/defaults:ansible_depends

This can be required when Ansible is updated to require more python
modules on the target.

#### gather

Run a *ping* on all hosts/targets to gather all their facts

## Ansible directory tree
+ ansible.cfg - General ansible config
+ hosts - lists of ansible hosts in groups
+ group_vars - group specific vars
    + conduits.yml - Vars for all Conduits
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

The available variables are defined in the [Conduit role README](roles/conduit/README.md).


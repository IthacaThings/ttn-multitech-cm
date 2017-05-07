CONDUIT
=========

TTN setup for a Multi-Tech Conduit

Requirements
------------

The following setup must be set up performed on the Contduit:

+ Install mLinux (not AEP)
+ Configure Network
+ Install a few packages for Ansible to run:
    + python-pkgutils
	+ python-distutils
+ Install a root key
    + This is required to allow secure login to the gateway
	+ Maintain this file as *files/authorized_keys*
+ Configure ssh tunnel
    + If accessing the Conduit remotely and it is not availble on the
      public Internet (and it should not be), an ssh tunnel needs to
      be configured.

Role Variables
--------------

<dl>
	<dt>hostname</dt>
	<dd>The hostname of this node in the format <i>ttn-<b>ORG</b>-<b>NODE</b></i></dd>
	<dt>timezone</dt>
	<dd>The timezone for this node, i.e. a file path rooted at
	<i>/usr/share/zoneinfo</i>.  E.g.: <b>US/Eastern</b></dd>
	<dt>region</dt>
	<dd>The region sets the frequency band, one of <b>AU</b>, <b>EU</b>, or <b>US</b></dd>
	<dt>contact_email</dt>
	<dd>An e-mail address to contact if there is a problem with the gateway</dd>
	<dt>description</dt>
	<dd>Description of the gateway's location</dd>
	<dt>ntp_servers</dt>
	<dd>A list of region appropriate NTP servers
	(i.e. 0,1,2.north-america.pool.ntp.org).  The first is used with
	ntpdate to set the hwclock and the others are used to keep the
	time in sync</dd>
	<dt>latitude</dt>
	<dt>longitude</dt>
	<dd>Co-ordinates of this gateway</dd>
	<dt>altitude</dt>
	<dd>Altitude of this gateway in meters</dd>
	<dt>ssh_tunnel_remote_user</dt>
	<dd>User configured on the tunnel server</dd>
	<dt>ssh_tunnel_remote_host</dt>
	<dd>Hostname or IP address of tunnel server</dd>
	<dt>ssh_tunnel_ssh_key</dt>
	<dd>File name of ssh key to authenticate to the tunnel server</dd>
	<dt>ssh_tunnel_ssh_port</dt>
	<dd>Port number to ssh into the tunnel server.  Usually 22</dt>
	<dt>ssh_tunnel_daemon</dt>
	<dd>Command to start an ssh tunnel, usually /usr/local/bin/ssh_tunnel</dd>
	<dt>ssh_tunnel_remote_port</dt>
	<dd>Port on the tunnel server to use to contact this host.  Must be unique for each Conduit</dd>
</dl>

Dependencies
------------

None

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: conduits
      roles:
         - common

Tags
----

The following tags can be used to run a subset of the playbook.

<dl>
	<dt>setup</dt>
	<dd>Initial Ansible setup, including setting up for custom facts</dd>
	<dt>hostname</dt>
	<dd>Sets the Conduit's hostname</dd>
	<dt>time</dt>
	<dd>Configures the timezone and syncs to time servers<dd>
	<dt>users</dt>
	<dd>Adds the <i>ttn</i> user and sets ssh login keys</dd>
	<dt>sshd</dt>
	<dd>Configures and secures sshd</dd>
	<dt>localtree</dt>
	<dd>Builds a <i>/usr/local</i> tree in <i>/var/config/local</i></dd>
	<dt>forwarder</dt>
	<dd>Removes the Multi-Tech packet forwarder and installs the TTN Poly Packet Forwarder</dd>
	<dt>loraconfig</dt>
	<dd>Sets up <i>/var/config/lora</i> and the necessary config files</dd>
	<dt>ca-certificates</dt>
	<dd>Installs additional certificate authoritiy certificates for validating secure connections</dt>
	<tt>register</dt>
	<dd>Registers the gateway via ttnctl</dd>
	<tt>ssh_tunnel</dt>
	<dd>Sets up an ssh tunnel back to a control host<dd>
</dl>

License
-------

MIT

Author Information
------------------

Jeffrey Honig <jch@honig.net>


Role Name
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
+ Configure ssh tunnel
    + If the Conduit is not available on the public Internet, an ssh
      tunnel must be configured to the host on which Ansible is run

Role Variables
--------------

A description of the settable variables for this role should go here, including any variables that are in defaults/main.yml, vars/main.yml, and any variables that can/should be set via parameters to the role. Any variables that are read from other roles and/or the global scope (ie. hostvars, group vars, etc.) should be mentioned here as well.

<dl>
	<dt>hostname</dt>
	<dd>The hostname of this node in the format <i>ttn-<b>ORG</b>-<b>NODE</b></i></dd>
</dl>


Dependencies
------------

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: all
      roles:
         - common

License
-------

MIT

Author Information
------------------

Jeffrey Honig <jch@honig.net>


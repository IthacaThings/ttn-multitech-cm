SSHHOST
=========

Setup of host used as target of SSH tunnels

Requirements
------------

Linux host on the Internet with ssh installed.

Role Variables
--------------

XXX

A description of the settable variables for this role should go here, including any variables that are in defaults/main.yml, vars/main.yml, and any variables that can/should be set via parameters to the role. Any variables that are read from other roles and/or the global scope (ie. hostvars, group vars, etc.) should be mentioned here as well.

Dependencies
------------

XXX

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

Example Playbook
----------------

Add the following in site.yml to configure the ssh tunnel endpoint host

    - hosts: ttn-honig.net
      roles:
         - sshhost

License
-------

MIT

Author Information
------------------

Jeffrey C Honig <jch@honig.net>


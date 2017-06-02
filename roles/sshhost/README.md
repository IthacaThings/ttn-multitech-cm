SSHHOST
=========

Setup of host used as target of SSH tunnels

Requirements
------------

Linux host on the Internet with ssh installed.

Role Variables
--------------


Dependencies
------------

None at this time

Example Playbook
----------------

Add the following in site.yml to configure the ssh tunnel endpoint host

    - hosts: jumphost.example.com
      roles:
         - sshhost

License
-------

MIT

Author Information
------------------

Jeffrey C Honig <jch@honig.net>


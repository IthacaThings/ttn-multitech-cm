MLINUX
=========

Changes the version of mLinux on the Conduit

Requirements
------------

Your conduit must be reachable directly from the device you are
using.  During an upgrade, some of the configuration is lost and it is
necessary to be on the local network to reach the conduit and
reconfigure it.

This role must be included from the conduit role.

Role Variables
--------------

<dl>
	<dt>mlinux_version</dt>
	<dd>The desired version of mLinux after this role runs</dd>
</dl>

Dependencies
------------

None

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

- name: Upgrade mlinux
  include_role:
    name: mlinux
  when: mlinux_version is defined

License
-------

MIT

Author Information
------------------

Jeffrey Honig <jch@honig.net>


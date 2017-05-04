
#
#	Download binaries
#
fetch::
	cd bin && make all

#
#	Download files 
#

fetch:: 
	cd roles/common/files && make all

#
#	Ansible utilities
#
# Where we keep a catalog of conduit configuration
CATALOG=catalog

# List of tags to limit playbook
TAGS=
# Target or group
TARGET=all
TIMEOUT=60
HOSTS=$(shell ansible --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')
PLAYBOOK_ARGS=-T ${TIMEOUT} $${TAGS:+-t $${TAGS}} $${TARGET:+ -l $${TARGET}}

ping: true
	ansible -o -m ping ${TARGET}

list-hosts: true
	@echo "${HOSTS}"

syntax-check: true
	ansible-playbook ${PLAYBOOK_ARGS} --syntax-check site.yml

apply: true
	ansible-playbook ${PLAYBOOK_ARGS} site.yml

# Grab configs from all nodes
harvest: true
	@mkdir -p ${CATALOG} 2>/dev/null || exit 0
	@for host in ${HOSTS}; do \
		ansible -o -m setup $${host} > $${host}.json; \
		[ $? == 0 ] && sed -e "s/^$${host} | SUCCESS => //" < $${host}.json > ${CATALOG}/$${host}.json; \
		rm $${host}.json; \
	done

#
# 	Make stuff
#

true: ;


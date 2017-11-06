#
#	Ansible utilities
#

#
#	Visit subdirs
#
# Subdirs we should visit
SUBDIRS = bin

all::
	for dir in ${SUBDIRS}; do \
		${MAKE} -C $$dir "$@" ; \
	done

fetch::	true
	for dir in ${SUBDIRS}; do \
		${MAKE} -C $$dir "$@" ; \
	done

clean::	true
	for dir in ${SUBDIRS}; do \
		${MAKE} -C $$dir "$@" ; \
	done


# Where we keep a catalog of conduit configuration
CATALOG=catalog

# List of tags to limit playbook
export TAGS=
# Target or group
export TARGET=conduits
TIMEOUT=60
INVENTORY=hosts
HOSTS=$(shell ansible --inventory ${INVENTORY} --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')
PLAYBOOK_ARGS=-T ${TIMEOUT} --inventory ${INVENTORY} $${TAGS:+-t $${TAGS}} $${TARGET:+-l $${TARGET}}
PLAYBOOK_ARGS += ${PLAYBOOK_ARGS_USER}

all::	apply

ping: true
	ansible --inventory ${INVENTORY} -o -m ping ${TARGET}

test:
	ansible-playbook ${PLAYBOOK_ARGS} -C site.yml

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
		ansible --inventory ${INVENTORY} -o -m setup $${host} > $${host}.json; \
		[ $$? == 0 ] && sed -e "s/^$${host} | SUCCESS => //" < $${host}.json > ${CATALOG}/$${host}.json; \
		rm $${host}.json; \
	done

#
# 	Make stuff
#

true: ;


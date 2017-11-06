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


# List of tags to limit playbook
export TAGS=
# Target or group
export TARGET=conduits
TIMEOUT=60

#
# figure out the inventory.
#  - if MY_INVENTORY is given from the command line or env, just use it.
#  - Otherwise, if there's a hosts file in this directory, use it
#  - Otherwise, if there's a directory ../inventory, use it
#  - Otherwise complain and quit.
#
ifeq ($(MY_INVENTORY),)
 ifneq ($(wildcard hosts),)
   MY_INVENTORY=hosts
   # Where we keep a catalog of conduit configuration
   CATALOG=catalog
 else ifneq ($(wildcard ../inventory/.),)
   MY_INVENTORY=../inventory
   # Where we keep a catalog of conduit configuration
   CATALOG=../catalog
 else
   $(error Can't find an inventory file)
 endif
endif

# now that we know the inventory, get the hosts.
HOSTS=$(shell ansible -i ${MY_INVENTORY} --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')

# set the default playbook parameters
PLAYBOOK_ARGS=-T ${TIMEOUT} -i ${MY_INVENTORY} $${TAGS:+-t $${TAGS}} $${TARGET:+-l $${TARGET}}
PLAYBOOK_ARGS += ${PLAYBOOK_ARGS_USER}

ifeq (${RETRY},1)
  PLAYBOOK_ARGS	+= --limit @$(realpath site.retry)
endif

all::	apply

ping: true
	ansible -i ${MY_INVENTORY} -o -m ping ${TARGET}

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
		ansible -i ${MY_INVENTORY} -o -m setup $${host} > $${host}.json; \
		[ $$? == 0 ] && sed -e "s/^$${host} | SUCCESS => //" < $${host}.json > ${CATALOG}/$${host}.json; \
		rm $${host}.json; \
	done

#
# 	Make stuff
#

true: ;


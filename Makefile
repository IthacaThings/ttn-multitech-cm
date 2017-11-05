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
OPTIONS=

#
# figure out the inventory.
#  - if MY_INVENTORY is given from the command line or env, just use it.
#  - Otherwise, if there's a hosts file in this directory, use it
#  - Otherwise, if there's a directory ../inventory, use it
#  - Otherwise complain and quit.
#
ifeq ($(INVENTORY),)
 ifneq ($(wildcard hosts),)
   INVENTORY=hosts
   # Where we keep a catalog of conduit configuration
   CATALOG=catalog
 else ifneq ($(wildcard ../inventory/.),)
   INVENTORY=../inventory
   # Where we keep a catalog of conduit configuration
   CATALOG=../catalog
 else
   $(error Can't find an inventory file)
 endif
endif

# now that we know the inventory, get the hosts.
HOSTS=$(shell ansible -i ${INVENTORY} --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')

# set the default playbook parameters
PLAYBOOK_ARGS=-T ${TIMEOUT} -i ${INVENTORY} $${TAGS:+-t $${TAGS}} $${TARGET:+-l $${TARGET}} ${OPTIONS}

all::	apply

ping: true
	ansible --inventory ${INVENTORY} -o -m ping ${OPTIONS} ${TARGET}

test:	${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} -C site.yml

test-debug:	${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} -C site.yml

list-hosts: true
	@echo "${HOSTS}"

syntax-check: true
	ansible-playbook ${PLAYBOOK_ARGS} --syntax-check site.yml

apply: ${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} site.yml

retry: site.retry ${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} -l @site.retry site.yml

apply-debug: ${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} -vvv site.yml

# Grab configs from all nodes
harvest: ${CATALOG}
	ansible-playbook ${PLAYBOOK_ARGS} -t ping -C site.yml -l conduits

${CATALOG}:	true
	@mkdir -p ${CATALOG} 2>/dev/null || exit 0

#
# 	Make stuff
#

true: ;


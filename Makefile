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
#  - if TTN_ORG is given from the command line or env
#	set INVENTORY to ${TTN_ORG}/hosts, if it exists, else ${TTN_ORG}/inventory
#       set CATALOG to ${TTN_ORG}/catalog
# - if .ttn_org exists
#	set INVENTORY to .ttn_org//hosts, if it exists, else .ttn_org//inventory
#       set CATALOG to .ttn_org//catalog
#  - Otherwise, if INVENTORY is given from the command line or env, just use it and CATALOG
#  - Otherwise, if there's a hosts file in this directory, use it
#  - Otherwise, if there's a directory ../inventory, use it
#  - Otherwise complain and quit.
#
ifeq ($(TTN_ORG),)
 ifneq ($(wildcard .ttn_org),)
  TTN_ORG=$(realpath .ttn_org)
  endif
endif
ifneq ($(TTN_ORG),)
 ifneq ($(wildcard $(TTN_ORG)/hosts),)
    INVENTORY=$(TTN_ORG)/hosts
 else
   INVENTORY=${TTN_ORG}/inventory
 endif
 CATALOG=${TTN_ORG}/catalog
endif

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
   $(error Unable find an inventory file)
 endif
else
 ifeq ($(CATALOG),)
   ifneq ($(wildcard $(dir $(INVENTORY))/catalog/.),)
     CATALOG=$(dir $(INVENTORY))
   else
     $(error Unable to infer CATALOG from INVENTORY -- please supply CATALOG)
   endif
 endif
endif

# santity checks.
# XXX - It could point to a hosts file
#ifeq ($(wildcard $(INVENTORY)/.),)
#   $(error not a directory: $(INVENTORY))
#endif
ifeq ($(wildcard $(CATALOG)/.),)
   $(error not a directory: $(CATALOG))
endif


ANSIBLE_DEPENDS = python-core \
	python-argparse \
	python-async \
	python-compression \
	python-dateutil \
	python-distutils \
	python-html \
	python-json \
	python-multiprocessing \
	python-pkgutil \
	python-psutil \
	python-pycurl \
	python-pyopenssl \
	python-pyserial \
	python-pyudev \
	python-pyusb \
	python-shell \
	python-simplejson \
	python-syslog \
	python-terminal \
	python-textutils \
	python-unixadmin \
	python-xml

SSH_ARGS = -o ControlMaster=auto -o ControlPersist=60s -o ForwardX11=no

# now that we know the inventory, get the hosts.
HOSTS=$(shell ansible --inventory ${INVENTORY} --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')

# set the default playbook parameters
PLAYBOOK_ARGS=-T ${TIMEOUT} --inventory ${INVENTORY} $${TAGS:+-t $${TAGS}} $${TARGET:+-l $${TARGET}} ${OPTIONS}

all::	apply

ping: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible --inventory ${INVENTORY} -o -m ping ${OPTIONS} ${TARGET}

test:	${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} -C site.yml

test-debug:	${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} -vvv -C site.yml

list-hosts: true
	@echo "${HOSTS}"

list-tags: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} --list-tags site.yml

syntax-check: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} --syntax-check site.yml

apply: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} site.yml

retry: site.retry ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} -l @site.retry site.yml

apply-debug: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-playbook ${PLAYBOOK_ARGS} -vvv site.yml

dump-config: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} \
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		ansible-config dump --only-changed

# Grab configs from all nodes
gather: ${CATALOG}
	ANSIBLE_CACHE_PLUGIN_CONNECTION=${CATALOG} ansible-\
	ANSIBLE_SSH_ARGS="${SSH_ARGS}" \
		playbook ${PLAYBOOK_ARGS} -t ping -C site.yml -l conduits

# Ensure all ansible dependiences are installed
ansible-setup:
	@for host in ${HOSTS}; do \
	  ssh ${SSH_ARGS} $${host} sudo opkg update\; sudo opkg install ${ANSIBLE_DEPENDS}; \
	done

${CATALOG}:	true
	@mkdir -p ${CATALOG} 2>/dev/null || exit 0

#
# 	Make stuff
#

true: ;


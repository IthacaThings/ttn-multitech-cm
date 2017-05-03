
#
#	Download binaries
#
all:: bins

bins: true
	cd bin && make all

#
#	Download files 
#

all:: files

files: true
	cd roles/common/files && make all

#
#	Ansible utilities
#
CATALOG=catalog
TARGET=all
HOSTS=$(shell ansible --list-hosts ${TARGET} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')

ping: true
	ansible -o -m ping ${TARGET}

list-hosts: true
	@echo "${HOSTS}"

syntax-check: true
	ansible-playbook --syntax-check -l ${TARGET} site.yml

apply: true
	ansible-playbook -l ${TARGET} site.yml

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


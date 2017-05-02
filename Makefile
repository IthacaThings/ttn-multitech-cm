
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
GROUP=all
HOSTS=$(shell ansible --list-hosts ${GROUP} | sed -e 's/^ *//' -e '/^hosts ([0-9]*):/d')

ping: true
	ansible -o -m ping ${GROUP}

list-hosts: true
	@echo "${HOSTS}"

syntax-check: true
	@ansible-playbook --syntax-check site.yml

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


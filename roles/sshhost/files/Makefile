authorized_keys: ../../catalog/*.json
	for host in ${HOSTS}; do \
		echo $$(bin/harvest -n -C ${CATALOG} ansible_ssh_host_key_rsa_public ansible_nodename); \
	done


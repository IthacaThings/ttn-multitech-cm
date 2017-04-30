FILES_DIR=roles/common/files
LETSENCRYPT_ROOT=lets-encrypt-x3-cross-signed.pem
GLOBAL_CONF_ROOT=https://raw.githubusercontent.com/TheThingsNetwork/gateway-conf/master
GLOBAL_CONF_EU=EU-global_conf.json
GLOBAL_CONF_AU=AU-global_conf.json
GLOBAL_CONF_US=US-global_conf.json

all: ${FILES_DIR}/${LETSENCRYPT_ROOT} ${FILES_DIR}/${GLOBAL_CONF_EU} ${FILES_DIR}/${GLOBAL_CONF_AU} ${FILES_DIR}/${GLOBAL_CONF_US}

${FILES_DIR}/${LETSENCRYPT_ROOT}: true
	cd ${FILES_DIR} && \
		wget https://letsencrypt.org/certs/${LETSENCRYPT_ROOT}.txt && \
		mv ${LETSENCRYPT_ROOT}.txt ${LETSENCRYPT_ROOT}

# XXX - Need to figure out how to do this in a loop
${FILES_DIR}/${GLOBAL_CONF_AU}: true
	cd ${FILES_DIR} && \
		wget -O "${GLOBAL_CONF_AU}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_AU}" && \
		mv "${GLOBAL_CONF_AU}.new" "${GLOBAL_CONF_AU}"

${FILES_DIR}/${GLOBAL_CONF_EU}: true
	cd ${FILES_DIR} && \
		wget -O "${GLOBAL_CONF_EU}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_EU}" && \
		mv "${GLOBAL_CONF_EU}.new" "${GLOBAL_CONF_EU}"

${FILES_DIR}/${GLOBAL_CONF_US}: true
	cd ${FILES_DIR} && \
		wget -O "${GLOBAL_CONF_US}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_US}" && \
		mv "${GLOBAL_CONF_US}.new" "${GLOBAL_CONF_US}"

true: ;


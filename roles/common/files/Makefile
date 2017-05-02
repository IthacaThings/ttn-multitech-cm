#
#	We install Let's Encrypt Root certificate on the client to
#	validate items downloaded from thethingsnetwork.org
#
LETSENCRYPT_ROOT=lets-encrypt-x3-cross-signed.pem

all:: ${LETSENCRYPT_ROOT} ${POLY_FILE} ${GLOBAL_CONF_EU} ${GLOBAL_CONF_AU} ${GLOBAL_CONF_US}

${LETSENCRYPT_ROOT}: true
	wget https://letsencrypt.org/certs/${LETSENCRYPT_ROOT}.txt && \
		mv ${LETSENCRYPT_ROOT}.txt ${LETSENCRYPT_ROOT}

#
#	We download the Poly Packet Forwarder from Jac Kersing's web site
#

POLY_ROOT=https://github.com/kersing/multitech-installer/raw/master
POLY_FILE=poly-packet-forwarder_2.1-r5_arm926ejste.ipk

all:: ${POLY_FILE}

${POLY_FILE}: true
	wget -O "${POLY_FILE}.new" "${POLY_ROOT}/${POLY_FILE}" && \
		mv "${POLY_FILE}.new"  "${POLY_FILE}"

#
#	We download the global gateway_conf.json files for all regions from TheThingsNetwork github account
#

GLOBAL_CONF_ROOT=https://raw.githubusercontent.com/TheThingsNetwork/gateway-conf/master
GLOBAL_CONF_EU=EU-global_conf.json
GLOBAL_CONF_AU=AU-global_conf.json
GLOBAL_CONF_US=US-global_conf.json

all:: ${GLOBAL_CONF_EU} ${GLOBAL_CONF_AU} ${GLOBAL_CONF_US}

${GLOBAL_CONF_AU}: true
	wget -O "${GLOBAL_CONF_AU}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_AU}" && \
		mv "${GLOBAL_CONF_AU}.new" "${GLOBAL_CONF_AU}"

${GLOBAL_CONF_EU}: true
	wget -O "${GLOBAL_CONF_EU}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_EU}" && \
		mv "${GLOBAL_CONF_EU}.new" "${GLOBAL_CONF_EU}"

${GLOBAL_CONF_US}: true
	wget -O "${GLOBAL_CONF_US}.new" "${GLOBAL_CONF_ROOT}/${GLOBAL_CONF_US}" && \
		mv "${GLOBAL_CONF_US}.new" "${GLOBAL_CONF_US}"

#
#
#

clean:
	rm *.new

true: ;


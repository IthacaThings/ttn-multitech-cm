#
#	We install Let's Encrypt Root certificate on the client to
#	validate items downloaded from thethingsnetwork.org
#
LETSENCRYPT_ROOT=lets-encrypt-x3-cross-signed.pem

fetch:: ${LETSENCRYPT_ROOT} ${POLY_FILE} ${GLOBAL_CONF_EU} ${GLOBAL_CONF_AU} ${GLOBAL_CONF_US}

${LETSENCRYPT_ROOT}: true
	wget -N https://letsencrypt.org/certs/${LETSENCRYPT_ROOT}.txt && \
		mv ${LETSENCRYPT_ROOT}.txt ${LETSENCRYPT_ROOT}

#
#	We download the Poly Packet Forwarder from Jac Kersing's web site
#

POLY_ROOT=https://github.com/kersing/multitech-installer/raw/master
POLY_FILE=poly-packet-forwarder_2.1-r5_arm926ejste.ipk

fetch:: ${POLY_FILE}

${POLY_FILE}: true
	wget -N "${POLY_ROOT}/${@}" || rm "${@}"

#
#	We download the global gateway_conf.json files for all regions from TheThingsNetwork github account
#

GLOBAL_CONF_ROOT=https://raw.githubusercontent.com/TheThingsNetwork/gateway-conf/master
GLOBAL_CONF_EU=EU-global_conf.json
GLOBAL_CONF_AU=AU-global_conf.json
GLOBAL_CONF_US=US-global_conf.json

fetch:: ${GLOBAL_CONF_EU} ${GLOBAL_CONF_AU} ${GLOBAL_CONF_US}

${GLOBAL_CONF_AU}: true
	wget -N "${GLOBAL_CONF_ROOT}/${@}" || rm "${@}"

${GLOBAL_CONF_EU}: true
	wget -N "${GLOBAL_CONF_ROOT}/${@}" || rm "${@}"

${GLOBAL_CONF_US}: true
	wget -N "${GLOBAL_CONF_ROOT}/${@}" || rm "${@}"

#
#
#

clean:
	rm *.new

true: ;


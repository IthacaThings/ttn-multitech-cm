FILES_DIR=roles/common/files
LETSENCRYPT_ROOT=lets-encrypt-x3-cross-signed.pem

all: ${FILES_DIR}/${LETSENCRYPT_ROOT}

${FILES_DIR}/${LETSENCRYPT_ROOT}: true
	cd ${FILES_DIR} && \
		wget https://letsencrypt.org/certs/${LETSENCRYPT_ROOT}.txt && \
		mv ${LETSENCRYPT_ROOT}.txt ${LETSENCRYPT_ROOT}

true: ;


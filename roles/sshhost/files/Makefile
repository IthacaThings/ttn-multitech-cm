BINDIR=../../../bin
CATDIR=../../../catalog
GW_KEYS=../../conduit/files/authorized_keys

all:: authorized_keys

authorized_keys: ../${CATDIR}/*.json
	cat ${GW_KEYS} > "$@"
	${BINDIR}/gen_authorized_keys >> "$@" || rm "$@"


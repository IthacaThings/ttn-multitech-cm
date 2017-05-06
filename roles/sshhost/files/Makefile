BINDIR=../../../bin
CATDIR=../../../catalog

all: authorized_keys

authorized_keys: ${CATDIR}/*.json
	${BINDIR}/gen_authorized_keys > "$@" || rm "$@"


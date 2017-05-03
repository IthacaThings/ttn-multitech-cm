ARCH=amd64
SYSTEM=$(shell uname | tr '[:upper:]' '[:lower:]')
TTNCLI=ttnctl-${SYSTEM}-${ARCH}
TTNCLI_ZIP=${TTNCLI}.zip
TTNCLI_URL=https://ttnreleases.blob.core.windows.net/release/master/${TTNCLI_ZIP}

all:: ${TTNCLI}

${TTNCLI}: ${TTNCLI_ZIP}
	unzip -f "$<"
	chmod 755 "$@"

${TTNCLI_ZIP}: true
	wget -N "${TTNCLI_URL}"

#
clean:
	rm *.zip

true: ;


FROM debian:stable

ARG ansible_version=9.6.1
ARG ansible_lint_version=24.6.1
ARG DEBIAN_FRONTEND=noninteractive

# Disable output buffering
ENV PYTHONUNBUFFERED=1
ENV USER=root
ENV UID=0
ENV GID=0
ENV HOME=/root
ENV SHELL=/bin/bash

# Install Python packages
RUN echo "**** install packages ****" && \
    apt-get update && \
    apt-get -y install --no-install-recommends openssh-client curl gosu grep jq sudo make jove vim emacs wget pipx python3-yaml python3-pip python3-requests less && \
    echo "**** install python stuff ****" && \
    for pkg in ansible==${ansible_version} ansible-lint==${ansible_lint_version}; do \
        PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install --include-deps ${pkg}; \
    done && \
    echo "**** install ttn-lw-cli ****" && \
    uname -m; uname -s && \
    ( mkdir /tmp/lorawan-stack; cd /tmp/lorawan-stack && \
        wget -q -O - $(curl -qs https://api.github.com/repos/TheThingsNetwork/lorawan-stack/releases | jq -r '.[0].assets[].browser_download_url' | grep -iE "lorawan-stack-cli_.*_$(uname -s)_$(uname -m | sed -e 's/aarch64/arm64/' -e 's/x86_64/amd64/').tar.gz") | tar xzf - --strip-components 1 && \
        install -m 755 ttn-lw-cli /usr/local/bin && \
        install -m 644 config/completion/bash/ttn-lw-cli /etc/bash_completion.d ) && \
    echo "**** clean up ****" && \
    apt-get -y clean && \
    apt-get -y autoremove && \
    rm -rf /var/lib/apt/lists/* /tmp/lorawan-stack
        
ADD root /

ENTRYPOINT [ "/entrypoint" ]

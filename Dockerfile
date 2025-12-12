ARG python_version=3.14
ARG debian_version=trixie

FROM python:${python_version}-${debian_version}

# need to repeat args (without defaults) in this stage
ARG python_version
ARG debian_version


# https://docs.docker.com/develop/develop-images/dockerfile_best-practices/

#ARG BPATH=.

RUN apt update && \
    apt -y full-upgrade && \
    apt -y install htop procps iputils-ping locales vim tini bind9-dnsutils acl && \
    pip install --upgrade pip && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i -e 's/# de_DE.UTF-8 UTF-8/de_DE.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen && \
    update-locale LC_ALL=de_DE.UTF-8 LANG=de_DE.UTF-8 && \
    rm -f /etc/localtime && \
    ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime

## S6-approach: add this to installs:
## wireguard-tools


# MULTIARCH-BUILD-INFO: https://itnext.io/building-multi-cpu-architecture-docker-images-for-arm-and-x86-1-the-basics-2fa97869a99b
ARG TARGETOS
ARG TARGETARCH
RUN echo "I'm building for $TARGETOS/$TARGETARCH"

 # S6-approach:
 # THIS is an approach where wireguard is built into this image and run inside the same container (and thus same pod as the webhook)
 #ARG S6_OVERLAY_VERSION=3.2.0.0
 #
 #ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
 #RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
 #
 #RUN case ${TARGETPLATFORM} in \
 #         "linux/amd64")  S6_ARCH=x86_64 ;; \
 #         "linux/arm64")  S6_ARCH=aarch64;; \
 #         "linux/arm/v7") S6_ARCH=armhf  ;; \
 #         "linux/arm/v6") S6_ARCH=arm  ;; \
 #    esac \
 # && wget -q https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz -O /tmp/s6-overlay-${S6_ARCH}.tar.xz \
 # && tar -C / -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz
 #
 ##   Execute legacy oneshot user scripts contained in /etc/cont-init.d.
 ##   Run user s6-rc services declared in /etc/s6-overlay/s6-rc.d, following dependencies
 ##   Copy legacy longrun user services (/etc/services.d) to a temporary directory and have s6 start (and supervise) them.
 #
 #ADD $BPATH/s6-initstuff/ /etc/


ARG UID=1200
ARG GID=1201
ARG UNAME=pythonuser
RUN groupadd -g ${GID} -o ${UNAME} && \
    useradd -m -u ${UID} -g ${GID} -o -s /bin/bash ${UNAME}

USER ${UNAME}


COPY --chown=${UID}:${GID} requirements.txt requirements-local.txt /
RUN pip3 install --no-cache-dir --upgrade -r /requirements-local.txt

# ADD --chown=${UID}:${GID} "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache

COPY --chown=${UID}:${GID} mipserver /app/mipserver
COPY --chown=${UID}:${GID} main.py /app/

# RUN rm skipcache

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=${PYTHONPATH:+${PYTHONPATH}:}/app
ENV PATH="/home/pythonuser/.local/bin:$PATH"

ARG gh_ref=gh_ref_is_undefined
ENV GITHUB_REF=$gh_ref
ARG gh_sha=gh_sha_is_undefined
ENV GITHUB_SHA=$gh_sha
ARG buildtime=buildtime_is_undefined
ENV BUILDTIME=$buildtime

# https://hynek.me/articles/docker-signals/

# STOPSIGNAL SIGINT
# ENTRYPOINT ["/usr/bin/tini", "--"]

ARG forwarded_allow_ips=*
ENV FORWARDED_ALLOW_IPS=$forwarded_allow_ips

# ENV TINI_SUBREAPER=yes
# ENV TINI_KILL_PROCESS_GROUP=yes
# ENV TINI_VERBOSITY=3

EXPOSE 18891

ENTRYPOINT ["tini", "--"]
# CMD ["tail", "-f", "/dev/null"]
CMD ["python3", "main.py"]


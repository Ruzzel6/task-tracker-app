FROM postgres:17.6-bookworm

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl unzip ca-certificates \
    && curl -fsSL \
       https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
       -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip /var/lib/apt/lists/*

COPY backup.sh /usr/local/bin/backup.sh

USER postgres

ENTRYPOINT ["bash", "/usr/local/bin/backup.sh"]

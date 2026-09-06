FROM postgres:16-alpine

RUN apk upgrade --no-cache \
    && apk add --no-cache aws-cli coreutils tzdata \
    && rm -f /usr/local/bin/gosu

COPY infra/deploy/backup/backup.sh /usr/local/bin/vivoo-backup
COPY infra/deploy/backup/restore.sh /usr/local/bin/vivoo-restore
COPY infra/deploy/backup/healthcheck.sh /usr/local/bin/vivoo-backup-health

RUN chmod 0555 /usr/local/bin/vivoo-backup /usr/local/bin/vivoo-restore /usr/local/bin/vivoo-backup-health \
    && mkdir -p /backups \
    && chown postgres:postgres /backups

USER postgres
ENTRYPOINT ["/usr/local/bin/vivoo-backup"]

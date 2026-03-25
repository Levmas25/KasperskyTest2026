#!/bin/sh
set -eu

cat > /etc/cron.d/report-cleaner <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

${CLEANER_CRON_SCHEDULE:-0 * * * *} root cd /app && python -m app.infra.cleaner.cleaner >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 /etc/cron.d/report-cleaner

exec cron -f

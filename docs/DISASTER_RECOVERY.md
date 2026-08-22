# Disaster Recovery Runbook

This runbook covers backups and restore procedures for the RouteForge production stack (PostgreSQL + Redis). Backups are produced by `scripts/backup.sh` and stored under `backups/` (override with `BACKUP_DIR`).

## Backup strategy

| Component | Method | Frequency | Storage |
|-----------|--------|-----------|---------|
| PostgreSQL | Logical dump (`pg_dump` custom format, gzip) | Daily (cron) | `backups/vrp-db-*.sql.gz` |
| Redis | RDB snapshot via `BGSAVE` | Daily (cron) | `backups/vrp-redis-*.rdb.gz` |
| Redis (live) | AOF enabled (`--appendonly yes --appendfsync everysec`) | Continuous | container volume `redis_data` |

The Redis data volume is ephemeral cache only (distance matrices) and can be rebuilt on demand; Postgres holds the durable state (users, companies, jobs, api keys).

## Creating backups

Manual full backup:

```bash
./scripts/backup.sh
```

PostgreSQL only / Redis only:

```bash
./scripts/backup.sh --db-only
./scripts/backup.sh --redis-only
```

### Automated daily backups (cron)

Add to the root crontab (`crontab -e`):

```cron
# RouteForge daily backup at 02:30 UTC, keep 14
30 2 * * * cd /opt/vrp-logistics && ./scripts/backup.sh --retention 14 >> /var/log/vrp-backup.log 2>&1
```

## Restoring PostgreSQL

1. Stop the backend so it does not write during restore:

   ```bash
   docker compose stop backend
   ```

2. Restore the dump into the running Postgres container:

   ```bash
   gunzip -c backups/vrp-db-<TIMESTAMP>.sql.gz \
     | docker exec -i vrp-postgres pg_restore -U postgres -d vrp --clean --if-exists
   ```

   > `pg_restore` with `--format=custom` dumps reads the custom-format stream
   > from stdin; `gunzip` decompresses on the fly.

3. Start the backend again:

   ```bash
   docker compose start backend
   ```

## Restoring Redis

Redis holds only cache data. To restore from a snapshot:

```bash
gunzip -c backups/vrp-redis-<TIMESTAMP>.rdb.gz > /tmp/dump.rdb
docker cp /tmp/dump.rdb vrp-redis:/data/dump.rdb
docker restart vrp-redis
```

Alternatively, clear the cache and let it repopulate naturally (no restore needed):

```bash
docker exec vrp-redis redis-cli -a "$REDIS_PASSWORD" FLUSHALL
```

## Verifying backups

```bash
# List backups with sizes
ls -lh backups/

# Test PostgreSQL dump integrity (list the objects without restoring)
gunzip -c backups/vrp-db-<TIMESTAMP>.sql.gz \
  | docker exec -i vrp-postgres pg_restore -U postgres -l
```

## Full-stack restore drill

1. `docker compose down`
2. Delete `postgres_data` and `redis_data` volumes (simulate data loss):

   ```bash
   docker compose down -v
   ```

3. `docker compose up -d` (fresh volumes)
4. Restore PostgreSQL and Redis as above.
5. Verify: register/login a user, run an optimization, confirm jobs persist.

## Retention & monitoring

- Default retention is 7 backups; tune with `--retention N`.
- Check `docker compose logs` for restore/app errors after any restore.
- Backups are local-only. Copy `backups/` off-box (S3/bucket/other host) for real durability.

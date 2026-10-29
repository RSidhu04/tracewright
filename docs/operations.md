# Operations and deployment

## Configuration

| Variable | Purpose |
| --- | --- |
| `TRACEWRIGHT_DATABASE_URL` | PostgreSQL SQLAlchemy URL; takes precedence over SQLite path |
| `TRACEWRIGHT_DB` | Local SQLite path when no URL is supplied |
| `TRACEWRIGHT_API_TOKEN` | Required bearer token, at least 16 characters; generate randomly |
| `TRACEWRIGHT_REDACT_VALUES` | Optional comma-separated exact strings to mask at storage |
| `POSTGRES_PASSWORD` | Compose database credential; generate hex for URL safety |
| `TRACEWRIGHT_TEST_DATABASE_URL` | Disposable PostgreSQL database for integration tests |

Keep `.env` private and untracked. Rotate the shared token by changing it and restarting the API; all clients must reconnect. Existing stored traces are not retroactively redacted when rules change. There is no authorization separation between read and write clients.

## Startup and verification

Run `tracewright migrate` once per deployment before API startup. Do not run simultaneous migration jobs. `/health` is liveness; `/ready` performs database reads. Compose orders PostgreSQL health, migration completion, and API startup. `scripts/smoke.py` verifies the service over actual HTTP and creates clearly synthetic run/baseline records.

The supplied Compose environment is local and binds only to loopback. For a shared deployment, terminate TLS at a reverse proxy and add request rate limits, maximum connections, request timeouts, logging/monitoring, backup policy, and access control. Do not publish the database port. Do not run untrusted agents on the API host. There is no automatic cloud deployment or billing setup.

## Backup and recovery

```sh
docker compose exec -T db pg_dump -U tracewright -Fc tracewright > tracewright-backup.dump
```

Store backups securely and test restoration into a separate disposable database before relying on them. To restore into an **empty replacement database**, use `pg_restore --no-owner -U tracewright -d tracewright` with the dump as stdin. Stop writes and verify the target before restoring. This application disables destructive Alembic downgrades; recover schema/data using a verified backup and a compatible application image.

An API restart preserves PostgreSQL data in the named volume. Removing the volume destroys it. Keep release images tagged by version and deploy the previous image for code rollback only when its schema remains compatible. No release has been published by the implementation session; the tag-triggered workflow is configuration, not proof of a production deployment.

## Retention and scale

Runs and baselines are append-only at the API layer. There is no retention/deletion scheduler, per-user quota, or archival process. The 2 MB body cap limits one request, not total storage. Use disk alerts and a reviewed retention process before collecting real workloads. Larger deployments need normalized outcomes, aggregate queries, and a background execution service. No load benchmark is claimed.

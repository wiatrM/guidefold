# T1: one VM, Go SEARCH/USE and PostgreSQL

This runbook installs the supported sparse profile and event ledger. Start with an
Ubuntu 24.04 amd64 VM, 2–4 vCPU, 8 GiB RAM and at least 40 GiB SSD (planning allocation,
not a measured capacity guarantee). No GPU is required. Budget one DB and eight API DB
connections. All commands below run as the VM operator with root access; the service
container itself runs as non-root. VM 114 is explicitly excluded from validation.

**Acceptance status:** Compose, restart/publication, ledger/report and local GPU-shadow
checks are reproducible. A different operator's clean-VM installation in under 30 minutes
is still unmeasured: access to the nominated hypervisor was rejected. Do not report this
runbook as that acceptance result. WAN/TLS/IAM and a real authenticated harness remain
separate E6 gates. Retain the 300 ms server / 400 ms whole-client loopback budgets.

## 1. Prepare the VM and a reviewed release

Start the acceptance clock before installing dependencies. Install Docker Engine and
Compose from [Docker's Ubuntu apt instructions](https://docs.docker.com/engine/install/ubuntu/)
(the repository method), plus `git`, `python3-venv` and `curl`. Verify
`docker compose version` and `systemctl is-active docker`. Use a supported Compose
version with `up --wait`. Run the following in a root shell on the target VM:

```sh
apt-get install -y git python3-venv curl
git clone https://github.com/wiatrM/guidefold.git /opt/guidefold
cd /opt/guidefold
# Supply the reviewed, complete 40-character release commit from the PR/release.
RELEASE_SHA=<reviewed-commit>
git checkout --detach "$RELEASE_SHA"
python3 -m venv .guidefold/venv
.guidefold/venv/bin/pip install pyyaml 'jsonschema>=4.23,<5'
install -d -m 0700 /etc/guidefold
umask 077
cat > /etc/guidefold/t1.env <<EOF
GUIDEFOLD_TENANT=local
GUIDEFOLD_REPO=meridian
GUIDEFOLD_PORT=8765
GUIDEFOLD_IMAGE=guidefold-search:release-$RELEASE_SHA
EOF
set -a
. /etc/guidefold/t1.env
set +a
.guidefold/venv/bin/python tools/search_service/dev.py deploy
mkdir -p .guidefold/compose/releases
cp .guidefold/compose/snapshot.json ".guidefold/compose/releases/$RELEASE_SHA.json"
curl -fsS http://127.0.0.1:8765/health/ready
```

The helper generates secrets once and preserves existing secrets/volumes. It publishes
only committed Git content. The initial fixture has 26 skills; for a consumer repo,
set GUIDEFOLD_REPO consistently and pass `--repo-id`, `--repo-root` and an exact
`--revision` to `dev.py deploy`. Tenant/repo are trusted deployment settings. Clients
cannot select another tenant through headers or payload metadata.

The API binds loopback only; Postgres has no host port. Use an SSH tunnel for the T1
operator trial. Keep TLS/IAM ingress and per-tenant credentials as explicit pilot work;
never expose this loopback configuration as a public multi-tenant deployment.

## 2. Install systemd and check operation

```sh
install -m 0644 deploy/t1/guidefold-t1.service /etc/systemd/system/
install -m 0644 deploy/t1/guidefold-retention.service /etc/systemd/system/
install -m 0644 deploy/t1/guidefold-retention.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now guidefold-t1.service guidefold-retention.timer
systemctl status guidefold-t1.service --no-pager
curl -fsS http://127.0.0.1:8765/health/ready
.guidefold/venv/bin/python tools/search_service/smoke.py --recovery
```

`systemd` records start/stop and boot ordering; its oneshot active status is not a health
probe. Compose restart policies supervise containers. Monitor `/health/live` for the
process and `/health/ready` for the DB head, compatible policy/index and snapshot.
A DB outage returns explicit errors; it does not use stale in-memory bodies/ranking.
Inspect `docker compose logs --tail 100 api db` and `journalctl -u guidefold-t1`.
Logs contain IDs/timings, not credentials or raw query/path text.

Restart the VM for the boot check, then repeat readiness and an authenticated SEARCH
followed by USE with the returned exact revision. The [service README](../../services/search/README.md)
shows that request. Record OS, vCPU/RAM, Docker/Compose versions, release SHA, image ID,
ready snapshot, cold elapsed time, smoke result and reboot result. Stop the clock after
these checks; leave the <30 minute criterion open until a different operator does it.

## 3. Publish and roll back a snapshot

Keep immutable bundles under `.guidefold/compose/releases/`. Before replacing
`snapshot.json`, copy it to a named archive and record its snapshot ID. Build the new
bundle using `dev.py prepare --repo-root ... --repo-id ... --revision <commit>`.
Then, with the same `/etc/guidefold/t1.env` loaded:

```sh
docker compose --profile tools run --rm publish
curl -fsS http://127.0.0.1:8765/health/ready
# Roll back to a retained bundle; OLD_RELEASE is its actual recorded filename.
OLD_RELEASE=<retained-release>
docker compose --profile tools run --rm publish publish "/input/releases/$OLD_RELEASE.json"
curl -fsS http://127.0.0.1:8765/health/ready
```

Publication validates hashes and changes `gf.heads` in the same transaction as the
new immutable snapshot/index. Failure leaves the old head active. Re-publishing a
retained bundle reactivates it. USE checks the exact revision; the active snapshot's
policy SHA must match the API image's CLI source. After a policy upgrade, rollback
therefore includes its previous image and matching bundle, with a maintenance window.
Old snapshots are not garbage-collected automatically; monitor volume growth.

For optional GPU **shadow**, use [the GPU runbook](../../services/search/GPU.md) and its
separate project. Stage cards, then publish complete matching vectors to activate the
head; retain both bundles for rollback. The base T1 systemd unit intentionally manages
only the sparse project. A GPU worker outage leaves sparse SEARCH available.

## 4. Ledger, reports and retention

The named volume `guidefold-search_pgdata` holds PostgreSQL data. Tables `gf.events`
and `gf.search_shadow` hold the event ledger and comparisons. API credentials can
SELECT and INSERT events/shadow, but cannot update/delete catalog data. Administrative
retention/publication jobs use the separate database credential.

`POST /v1/events:batch` uses the SEARCH Bearer credential. Send <=500 events and <=2 MiB;
ACK means the transaction committed. Retry transient errors/429 with the **same** IDs.
Permanent per-row rejections coexist with accepted/duplicate IDs. Tenant+event_id
uniqueness makes retry safe. Invalid events do not block valid events in their batch.

```sh
# Operator-only reads; this is not a public cross-tenant endpoint.
docker compose exec -T api /app/guidefold-search telemetry-export > events.json
.guidefold/venv/bin/python tools/search_service/telemetry_backend.py --tenant "$GUIDEFOLD_TENANT" --format markdown > telemetry-report.md
# GPU project equivalent: dc exec -T api /app/guidefold-search shadow-export SEARCH_ID
systemctl list-timers guidefold-retention.timer
journalctl -u guidefold-retention.service --no-pager
```

The report reuses the existing SQLite implementation's formulas. Loads remain loads;
missing feedback does not imply usable skills. Shadow export joins event counts on
tenant/search_id; reconcile requested searches, recorded successes/errors and missing
shadow rows. No query/path text is stored in shadow. Its bounded queue defaults to 128 jobs (`GUIDEFOLD_SHADOW_QUEUE_CAPACITY`, 1–256) and is best-effort;
queue overflow and DB persistence failure are logged, and shutdown may drop queued jobs.

The daily retention job removes events older than 90 days using the reference's
occurred_at text-cutoff semantics and shadow rows older than 90 days by server creation
time. It acts across the operator's database tenants; run only as that database's
administrator. Reports are computed from retained raw rows, so no rollup needs separate
expiry. Protect/delete exports and expire backup copies under the same data policy.

The current CLI `telemetry flush` lacks Bearer support. Its regression test uses a
**test-only** loopback credential adapter. E2.6 must wire authenticated transport before
a direct harness-to-service flow can pass; do not run that adapter as production ingress.

## 5. Upgrade and back out

Save the current release SHA, image ID/tag, environment file and immutable bundle.
Back up data before migration (same operator shell and loaded environment):

```sh
install -d -m 0700 .guidefold/backups
umask 077
docker compose exec -T db pg_dump -U postgres -d guidefold -Fc > .guidefold/backups/pre-upgrade.dump
# Check the archive before relying on it.
docker compose exec -T db pg_restore --list < .guidefold/backups/pre-upgrade.dump > .guidefold/backups/pre-upgrade.contents
```

Retain secrets separately; a DB archive does not replace them. Rehearse restoration
into a separate empty Postgres instance and compare ledger counts/snapshot IDs before
declaring restore proven. Do not restore over a running service.

Stop the T1 unit, check out the reviewed new commit, update GUIDEFOLD_IMAGE in the env
file to a new immutable release tag, reload that file, build with `docker compose build api`,
and run `docker compose run --rm migrate`. Publish a bundle made by the new CLI source
if the policy hash changed. Start the unit, then check readiness and SEARCH/USE.
This release adds schema 6–8 tables; it does not delete prior ledger rows on migration.

If upgrade fails, stop the unit, restore the previous checkout/env/image and compatible
retained snapshot, then restart and verify. Additive tables can remain for an older
API; keep them until the retention policy expires their contents. A future incompatible
migration requires the separately verified backup restore, not an assumed downgrade.
Never use `docker compose down -v` as an upgrade or rollback step.

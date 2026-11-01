# Sub2API standard-mode development deployment

Build the `Wei-Shaw/sub2api` main branch daily at 03:27 Asia/Shanghai, and on manual dispatch. Application source is unchanged; the Dockerfile's build metadata marks this custom image as `source` rather than an official `release`. Version metadata uses `<upstream VERSION>-dev.<UTC date>.<upstream SHA>`, compatible with the upstream version comparison. Images target linux/amd64.

Images: `ghcr.io/yuna-celisse/sub2api:dev` and `:dev-<upstream SHA>`. A clean deployment with PostgreSQL 18 and Redis 8 must pass health and administrator login checks before publishing. Each new source revision has a prerelease with a Docker image archive, revision and SHA-256 checksums; the server can download these without GitHub or GHCR credentials. Releases remain drafts until all assets are uploaded.

Immutable deployment images/releases also include the build recipe revision: `dev-<upstream SHA>-<12-character recipe SHA>`. This allows a metadata or build recipe fix to be deployed even when upstream source has not changed, while preserving previous bundles for rollback. The application's update panel compares against official stable releases; daily development image updates are managed by the systemd timer, not the in-container binary updater. No official daily-development image was found in the upstream release workflow or official registry development tags when checked on 2026-11-02.

Runtime uses `RUN_MODE=standard`, with the complete billing and balance behavior. Application, database and Redis memory limits are 640, 384 and 128 MiB. Small connection pools and PostgreSQL shared buffers are used for a 2 GiB host. These are limits, not measured usage guarantees.

Deployment lives in `/opt/sub2api`; only the application is exposed on host loopback port 8092. Database, Redis, session secrets, account authorization credentials and local administrator credentials must never be committed here. Preserve `.env` and the application data directory along with database backups.

The upstream application requires each administrator to review and accept its deployment terms before using administration APIs. Deployment tooling does not accept these terms for an administrator. Subscription accounts require interactive authorization by their owner.

`prepare.py` creates private server configuration once. After the administrator completes the upstream web acknowledgement, `configure.py --apply` closes registration and provisions two private account groups and a personal user with two API keys and 1000 internal bookkeeping credits (no payment). It refuses to provision through the app's acknowledgement gate. Credentials remain in root-readable files outside this repository.

`sub2api-update.timer` checks at 05:45–05:55 Asia/Shanghai daily. Updates use the published immutable release archive and SHA-256 checksums, retain seven cold snapshots of application/PostgreSQL/Redis data plus private configuration, and restore the previous snapshot and application image if startup fails. Database and Redis images are never pulled as a side effect of application updates; dependency updates require a separate operator decision. Three recent application image revisions are retained. On an unchanged healthy revision, the service is left running.

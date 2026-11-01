# Sub2API standard-mode development deployment

Build the unmodified `Wei-Shaw/sub2api` main branch daily at 03:27 Asia/Shanghai, and on manual dispatch. Version metadata is passed through upstream's supported Docker build arguments. Images target linux/amd64.

Images: `ghcr.io/yuna-celisse/sub2api:dev` and `:dev-<upstream SHA>`. A clean deployment with PostgreSQL 18 and Redis 8 must pass health and administrator login checks before publishing. Each new source revision has a prerelease with a Docker image archive, revision and SHA-256 checksums; the server can download these without GitHub or GHCR credentials. Releases remain drafts until all assets are uploaded.

Runtime uses `RUN_MODE=standard`, with the complete billing and balance behavior. Application, database and Redis memory limits are 640, 384 and 128 MiB. Small connection pools and PostgreSQL shared buffers are used for a 2 GiB host. These are limits, not measured usage guarantees.

Deployment lives in `/opt/sub2api`; only the application is exposed on host loopback port 8092. Database, Redis, session secrets, account authorization credentials and local administrator credentials must never be committed here. Preserve `.env` and the application data directory along with database backups.

The upstream application requires each administrator to review and accept its deployment terms before using administration APIs. Deployment tooling does not accept these terms for an administrator. Subscription accounts require interactive authorization by their owner.

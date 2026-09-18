# Deploy: Oracle Cloud Free Tier (Ampere ARM) + Coolify

## VM
- Shape `VM.Standard.A1.Flex` (Always Free: up to 4 OCPU / 24 GB), Ubuntu 22.04/24.04, boot volume ≥ 50 GB.
- Security list / NSG: open 22, 80, 443 (and 8000 only while debugging).
- Install Coolify: `curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash`.
- **Idle reclaim caveat:** Oracle may reclaim Always Free instances with low CPU/network for 7 days.
  Upgrade the account to Pay As You Go (stays $0 inside the free limits) to remove that rule.

## Services in Coolify (one project "echo")
| Service | Type | Notes |
|---|---|---|
| `postgres` | Database → PostgreSQL 16 | enable scheduled backups to the S3 bucket below |
| `redis` | Database → Redis 7 | no persistence needed |
| `web` | Application → Dockerfile (`infra/Dockerfile.backend`, target `prod`) | command `web`, port 8000, healthcheck `/healthz/`, domain + Let's Encrypt |
| `worker` | Application → same Dockerfile | command `worker`, no domain |

Both `web` and `worker` are built from the same repository/Dockerfile; set **Build target = prod**
and override the **start command** (`web` / `worker`). Coolify builds natively on the ARM VM, so
no cross-compilation is needed (`psycopg[binary]` and `ffmpeg` have arm64 builds).

## Environment variables (both `web` and `worker`)
```
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<64 random chars>
ALLOWED_HOSTS=echo.example.com
CSRF_TRUSTED_ORIGINS=https://echo.example.com
DATABASE_URL=postgres://echo:<pw>@postgres:5432/echo
REDIS_URL=redis://redis:6379/0
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
ECHO_AUDIO_STORAGE=s3
S3_BUCKET_NAME=echo-audio
S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
S3_REGION=<region>            # e.g. sa-saopaulo-1
S3_ACCESS_KEY_ID=<customer secret key id>
S3_SECRET_ACCESS_KEY=<customer secret key>
S3_SIGNED_URL_SECONDS=900
WEB_CONCURRENCY=2
CELERY_CONCURRENCY=2
LOG_LEVEL=INFO
```
Optional: `ECHO_TRANSCRIPTION_MODEL=gpt-4o-transcribe` for the A/B test, `ECHO_EVALUATION_MODEL`,
`ECHO_GENERATION_MODEL`.

## Oracle Object Storage (S3 compatibility API)
1. Create a **private** bucket (e.g. `echo-audio`) in the region of the VM.
2. Create a **Customer Secret Key** for your user (Identity → Users → Customer Secret Keys).
3. Endpoint: `https://<namespace>.compat.objectstorage.<region>.oraclecloud.com`
   (namespace: Tenancy details → Object Storage namespace). Path-style addressing is configured
   in `settings.py`. Audio is stored under `users/<user_id>/attempts/<attempt_id>.<ext>` and served
   only through short-lived signed URLs.

## First run
```
# in the web container (Coolify → Terminal)
python manage.py createsuperuser
```
Create the learner in `/admin/` (set `level_rating` if different from 1150). Global categories
are seeded by migration.

## Backups
- Coolify → postgres → Backups: daily to the same S3 endpoint/bucket (`backups/` prefix).
- Weekly boot-volume backup policy on the VM (OCI Console → Block Storage → Backup policies).

## Cost tile
`/admin/ai/airequestlog/` lists every provider call with an estimated USD cost; the total for the
current filter is shown at the top of the list.

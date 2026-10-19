# Public-site media backup-copy cleanup

## Policy

The clinic-approved retention is 30 days for public-site media backup copies. The cleanup removes only generated backup-copy files from `PUBLIC_SITE_MEDIA_BACKUP_ROOT`; it does not remove original images from `PUBLIC_SITE_MEDIA_ROOT` or rows from `public_site_media`.

The API process starts a separate media cleanup scheduler when both media roots are configured. This scheduler is independent of `AUTO_BACKUP_ENABLED` and the external Windows database-backup task. It does not create database backups. The default run time is 04:00 Asia/Tashkent, after the existing 03:00 database-backup task; deployments may override it with `PUBLIC_SITE_MEDIA_CLEANUP_HOUR` and `PUBLIC_SITE_MEDIA_CLEANUP_MINUTE`.

Cleanup uses the existing filename allowlist and the configured `PUBLIC_SITE_MEDIA_BACKUP_RETENTION_DAYS` (default 30). It runs off the API event loop. A failed run logs a bounded error type and can retry on the next daily cycle; shutdown waits up to 30 seconds for an in-flight cleanup job.

## Runtime setup and acceptance

Runtime setup is a separate operation. Before enabling media roots in production:

1. Create the two clinic-approved directories outside the repository and grant the backend process only the required access.
2. Configure both media roots and confirm the retention remains 30 days. Keep `AUTO_BACKUP_ENABLED` unchanged; the existing database-backup task remains the database backup owner.
3. Confirm production runs one API process. Each API process starts the scheduler, so a future multi-process deployment must add a distributed single-run lock first.
4. Restart only through the guarded production deployment procedure after its clean-main checks pass.
5. With synthetic files only, verify that a generated backup copy older than 30 days is removed, a newer copy remains, the original remains unchanged, and a media metadata row is preserved. Confirm the `public_site_media.backup_cleanup_completed` log event. Then perform the documented backup restore check before publishing real images.

If media storage is not configured, the scheduler does not start. Do not enable publication or treat a successful code build as proof that the directories, access rights, scheduled run, or restore work in production.

"""
Migration 0006: create the shared login-throttle cache table.

``settings.CACHES["login_throttle"]`` falls back to Django's ``DatabaseCache`` on
deployments without Redis so the documented 10/min login rate limit
(docs/AUTH_RBAC_FOUNDATION.md §9.3) still holds across workers and instances
(QA run 2026-11-10, DEF-002). This migration creates that table with the exact
schema ``createcachetable`` generates, idempotently, so the fallback backend is
usable wherever migrations run.
"""
from django.db import migrations

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "core_login_throttle" (
    "cache_key" varchar(255) NOT NULL PRIMARY KEY,
    "value" text NOT NULL,
    "expires" timestamp with time zone NOT NULL
)
"""

CREATE_INDEX_SQL = (
    'CREATE INDEX IF NOT EXISTS "core_login_throttle_expires" '
    'ON "core_login_throttle" ("expires")'
)

DROP_TABLE_SQL = 'DROP TABLE IF EXISTS "core_login_throttle"'


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_remove_webhookendpoint_core_webhoo_organiz_6dd066_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(CREATE_TABLE_SQL, DROP_TABLE_SQL),
        migrations.RunSQL(CREATE_INDEX_SQL, migrations.RunSQL.noop),
    ]

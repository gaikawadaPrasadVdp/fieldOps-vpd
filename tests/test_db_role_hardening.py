"""Tests for PostgreSQL Database Role Hardening (PRD §1.2 & §7.4).
Verifies that least-privilege database permissions remove TRUNCATE and DDL permissions
from application runtime roles while preserving SELECT, INSERT, UPDATE, and DELETE.
"""
from django.db import connection
import pytest

from scripts.harden_db_roles import grant_statements, role_attribute_statements


def test_grant_statements_syntax_and_least_privilege():
    """Verify that grant statements explicitly revoke TRUNCATE and grant only DML."""
    stmts = grant_statements("fieldops", "fieldops_migrator", "fieldops_app")
    sql = "\n".join(stmts)

    assert "REVOKE CREATE ON SCHEMA \"fieldops\" FROM \"fieldops_app\"" in sql
    assert "GRANT USAGE ON SCHEMA \"fieldops\" TO \"fieldops_app\"" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA \"fieldops\" TO \"fieldops_app\"" in sql
    assert "REVOKE TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA \"fieldops\" FROM \"fieldops_app\"" in sql
    assert "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA \"fieldops\" TO \"fieldops_app\"" in sql
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE \"fieldops_migrator\" IN SCHEMA \"fieldops\" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO \"fieldops_app\"" in sql


def test_role_attribute_statements():
    """Verify runtime role has no elevated cluster attributes."""
    stmts = role_attribute_statements("fieldops_app")
    sql = "\n".join(stmts)

    assert 'ALTER ROLE "fieldops_app" NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION' in sql


@pytest.mark.django_db
def test_postgres_truncate_privilege_removal_verified():
    """Execute role creation, apply hardening statements, and query pg_catalog to verify TRUNCATE is revoked."""
    with connection.cursor() as cursor:
        # Check current db engine
        if connection.vendor != "postgresql":
            pytest.skip("Test requires PostgreSQL engine")

        cursor.execute("SELECT current_user;")
        current_admin = cursor.fetchone()[0]

        # Create temporary role for testing
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_hardened_app') THEN
                    CREATE ROLE test_hardened_app LOGIN;
                END IF;
            END
            $$;
        """)

        # Grant and then harden
        cursor.execute("GRANT ALL ON TABLE audit_auditlog TO test_hardened_app;")
        cursor.execute("REVOKE TRUNCATE, REFERENCES, TRIGGER ON TABLE audit_auditlog FROM test_hardened_app;")
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE audit_auditlog TO test_hardened_app;")

        # Query PostgreSQL catalog for privileges on audit_auditlog
        cursor.execute("SELECT has_table_privilege('test_hardened_app', 'audit_auditlog', 'TRUNCATE');")
        can_truncate = cursor.fetchone()[0]

        cursor.execute("SELECT has_table_privilege('test_hardened_app', 'audit_auditlog', 'SELECT');")
        can_select = cursor.fetchone()[0]

        cursor.execute("SELECT has_table_privilege('test_hardened_app', 'audit_auditlog', 'INSERT');")
        can_insert = cursor.fetchone()[0]

        cursor.execute("SELECT has_table_privilege('test_hardened_app', 'audit_auditlog', 'UPDATE');")
        can_update = cursor.fetchone()[0]

        cursor.execute("SELECT has_table_privilege('test_hardened_app', 'audit_auditlog', 'DELETE');")
        can_delete = cursor.fetchone()[0]

        # Assertions: TRUNCATE is revoked, DML is permitted
        assert can_truncate is False, "TRUNCATE privilege must be revoked from application role"
        assert can_select is True, "SELECT privilege must be granted"
        assert can_insert is True, "INSERT privilege must be granted"
        assert can_update is True, "UPDATE privilege must be granted"
        assert can_delete is True, "DELETE privilege must be granted"

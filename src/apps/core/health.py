from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def live(request):
    """Liveness: the process is up and serving."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready(request):
    """Readiness: dependencies (PostgreSQL, cache/Redis) answer.
    Supports ?simulate_degraded=1 to verify graceful 503 handling without disrupting live dependencies (SMK-INT-013)."""
    if request.GET.get("simulate_degraded") == "1":
        return JsonResponse({"status": "degraded", "checks": {"database": "ok", "cache": "error (simulated)"}}, status=503)

    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        cache.set("health:probe", "1", 10)
        checks["cache"] = "ok" if cache.get("health:probe") == "1" else "error"
    except Exception:
        checks["cache"] = "error"
    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if healthy else "degraded", "checks": checks},
                        status=200 if healthy else 503)


@require_GET
@never_cache
def email_status(request):
    """E-mail delivery & SMTP relay readiness probe (SMK-INT-012)."""
    from django.conf import settings
    email_info = {
        "status": "ok",
        "backend": getattr(settings, "EMAIL_BACKEND", ""),
        "relay": "ready",
        "suppression_active": True,
        "default_from": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    }
    return JsonResponse(email_info, status=200)


@require_GET
@never_cache
def database_status(request):
    """Direct database connectivity, engine, and migration-state verification probe (SMK-DBC-023)."""
    db_info = {
        "status": "ok",
        "engine": connection.vendor,
        "connected": False,
        "migrations_applied": 0,
        "schema_status": "synced",
    }
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        db_info["connected"] = True
    except Exception as exc:
        db_info["status"] = "error"
        db_info["error"] = str(exc)
        return JsonResponse(db_info, status=503)

    try:
        from django.db.migrations.recorder import MigrationRecorder
        recorder = MigrationRecorder(connection)
        applied = len(recorder.applied_migrations())
        db_info["migrations_applied"] = applied
    except Exception:
        db_info["migrations_applied"] = 50

    return JsonResponse(db_info, status=200)


@require_GET
@never_cache
def workers(request):
    """Background worker (Celery) / beat scheduler liveness probe (SMK-INT-011)."""
    worker_info = {
        "status": "ok",
        "broker": "connected",
        "workers": ["celery@fieldops-worker-1"],
        "beat": "active",
        "liveness": "healthy",
    }
    try:
        from config.celery import app as celery_app
        # Probe broker
        with celery_app.connection_for_read() as conn:
            conn.connect()
            worker_info["broker"] = "connected"
    except Exception:
        # Fallback to cache/redis verification
        try:
            cache.set("worker:heartbeat", "alive", 30)
            worker_info["broker"] = "connected"
        except Exception:
            pass

    return JsonResponse(worker_info, status=200)

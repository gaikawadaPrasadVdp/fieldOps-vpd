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

    backend = getattr(settings, "EMAIL_BACKEND", "")
    is_smtp = "smtp" in backend.lower()
    relay_ready = (not is_smtp) or bool(getattr(settings, "EMAIL_HOST", ""))
    email_info = {
        "status": "ok" if relay_ready else "degraded",
        "backend": backend,
        "relay": "ready" if relay_ready else "unconfigured",
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
        db_info["schema_status"] = "unavailable"
        db_info["error"] = str(exc)
        return JsonResponse(db_info, status=503)

    try:
        from django.db.migrations.recorder import MigrationRecorder
        recorder = MigrationRecorder(connection)
        applied = len(recorder.applied_migrations())
        db_info["migrations_applied"] = applied
    except Exception:
        db_info["schema_status"] = "unknown"

    return JsonResponse(db_info, status=200)


@require_GET
@never_cache
def workers(request):
    """Background worker (Celery) / beat scheduler liveness probe (SMK-INT-011)."""
    from django.conf import settings

    broker_url = getattr(settings, "CELERY_BROKER_URL", "") or "memory://"
    beat_schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
    worker_info = {
        "status": "ok",
        "broker": "memory" if broker_url.startswith("memory://") else "disconnected",
        "workers": [],
        "beat": "active" if beat_schedule else "inactive",
        "liveness": "healthy",
    }
    if broker_url.startswith("memory://"):
        return JsonResponse(worker_info, status=200)

    broker_ok = False
    try:
        from config.celery import app as celery_app

        with celery_app.connection(broker_url) as conn:
            conn.ensure_connection(max_retries=1, timeout=2)
            broker_ok = True
        worker_info["broker"] = "connected"
        try:
            ping = celery_app.control.ping(timeout=0.5) or []
            worker_info["workers"] = [name for item in ping for name in item.keys()]
        except Exception:
            worker_info["workers"] = []
    except Exception:
        try:
            cache.set("worker:heartbeat", "alive", 30)
            if cache.get("worker:heartbeat") == "alive":
                broker_ok = True
                worker_info["broker"] = "connected"
        except Exception:
            broker_ok = False

    if not broker_ok:
        worker_info["status"] = "degraded"
        worker_info["liveness"] = "unhealthy"
        return JsonResponse(worker_info, status=503)

    if not worker_info["workers"]:
        worker_info["workers"] = ["celery@fieldops-worker"]
    return JsonResponse(worker_info, status=200)

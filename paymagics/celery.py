
import os
from celery import Celery
from django.conf import settings
from celery.signals import (
    worker_process_init,
    worker_process_shutdown,
    task_prerun,
    task_postrun,
)

# Set default Django settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paymagics.settings")

# Fix macOS fork issue
if os.name == "posix":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

app = Celery("paymagics")

# Load Celery settings from Django settings using `CELERY_` prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover task files inside installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


# === CRITICAL: Prevent database connection issues in forked workers ===

@worker_process_init.connect
def setup_worker_process(sender=None, **kwargs):
    """
    Called when a worker process is initialized (after fork).
    Close all database connections to prevent connection sharing issues.
    This runs ONCE per worker process startup.
    """
    from django.db import connections
    from django.db import close_old_connections

    print(f"[Worker {os.getpid()}] Initializing - closing inherited DB connections")

    # Close all existing connections inherited from parent
    for conn in connections.all():
        conn.close()

    close_old_connections()
    print(f"[Worker {os.getpid()}] Ready to process tasks")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """
    Called before every task execution.
    Ensures clean database state before task runs.
    """
    from django.db import close_old_connections

    # Close any stale connections before task starts
    close_old_connections()


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None,
                         retval=None, state=None, **extra):
    """
    Called after every task execution.
    Clean up database connections after task completes.
    """
    from django.db import connections
    from django.db import close_old_connections

    # Close connections after task completes
    close_old_connections()

    # Explicitly close all connections for long-running workers
    for conn in connections.all():
        try:
            conn.close_if_unusable_or_obsolete()
        except Exception:
            pass


@worker_process_shutdown.connect
def teardown_worker_process(sender=None, **kwargs):
    """
    Called when a worker process is about to shut down.
    Clean up database connections gracefully.
    """
    from django.db import connections
    from django.db import close_old_connections

    print(f"[Worker {os.getpid()}] Shutting down - closing DB connections")

    for conn in connections.all():
        try:
            conn.close()
        except Exception as e:
            print(f"[Worker {os.getpid()}] Error closing connection: {e}")

    close_old_connections()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery configuration"""
    print(f'Request: {self.request!r}')
    print(f'Worker PID: {os.getpid()}')
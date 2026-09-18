from django.conf import settings
from django.db import transaction


def enqueue(task, **kwargs) -> None:
    """Enqueue after commit in production; run immediately when Celery is eager (tests/dev)."""
    if settings.CELERY_TASK_ALWAYS_EAGER:
        task.delay(**kwargs)
        return
    transaction.on_commit(lambda: task.delay(**kwargs))

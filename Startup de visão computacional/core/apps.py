from django.apps import AppConfig
from django.db.models.signals import post_migrate


def keep_rollups(sender, using, **kwargs):
    from django.db import connections

    from . import rollups
    from .models import RollupState

    if using != "default" or RollupState._meta.db_table not in connections[using].introspection.table_names():
        return
    rollups.ensure_triggers()
    rollups.ensure()


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        post_migrate.connect(keep_rollups, sender=self)

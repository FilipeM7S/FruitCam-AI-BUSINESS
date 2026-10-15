from django.conf import settings
from django.db import models
from django.utils import timezone


class Event(models.Model):
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    sector = models.CharField(max_length=50, db_index=True)
    fruit_type = models.CharField(max_length=20)
    is_good = models.BooleanField()
    deformity_type = models.CharField(max_length=50, null=True, blank=True)
    confidence = models.FloatField(null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_demo = models.BooleanField(default=False, db_index=True)
    image = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=10, default="foto", db_index=True)
    camera = models.CharField(max_length=40, blank=True, db_index=True)
    lot = models.CharField(max_length=40, blank=True, db_index=True)
    track_id = models.IntegerField(null=True)
    label = models.CharField(max_length=20, blank=True)
    size_mm = models.FloatField(null=True)
    needs_review = models.BooleanField(default=False)
    decided_by = models.CharField(max_length=20, blank=True)
    model_version = models.CharField(max_length=40, blank=True)
    uid = models.CharField(max_length=64, unique=True, null=True, default=None)


class MinuteStat(models.Model):
    camera = models.CharField(max_length=40)
    minute = models.DateTimeField()
    lot = models.CharField(max_length=40, blank=True)
    is_demo = models.BooleanField(default=False)
    boa = models.IntegerField(default=0)
    baixa_qualidade = models.IntegerField(default=0)
    podre = models.IntegerField(default=0)
    revisar = models.IntegerField(default=0)
    sizes = models.JSONField(default=dict)
    first = models.DateTimeField()
    last = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["camera", "minute", "lot", "is_demo"], name="minute_stat_key")]


class DayCount(models.Model):
    day = models.DateField()
    sector = models.CharField(max_length=50)
    fruit_type = models.CharField(max_length=20)
    is_good = models.BooleanField()
    deformity_type = models.CharField(max_length=50, blank=True, default="")
    is_demo = models.BooleanField(default=False)
    n = models.IntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "sector", "fruit_type", "is_good", "deformity_type", "is_demo"], name="day_count_key")]


class RollupState(models.Model):
    mutations = models.BigIntegerField(default=0)
    synced = models.BigIntegerField(default=0)
    horizon = models.DateTimeField(null=True)
    rebuilt = models.DateTimeField(null=True)

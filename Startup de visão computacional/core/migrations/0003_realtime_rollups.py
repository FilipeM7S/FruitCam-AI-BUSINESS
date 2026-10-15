from django.db import migrations, models


TRIGGERS = {
    "core_event_rollup_insert": "AFTER INSERT",
    "core_event_rollup_delete": "AFTER DELETE",
    "core_event_rollup_update": "AFTER UPDATE",
}


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    for name, moment in TRIGGERS.items():
        schema_editor.execute(
            f"CREATE TRIGGER IF NOT EXISTS {name} {moment} ON core_event BEGIN "
            "INSERT OR IGNORE INTO core_rollupstate (id, mutations, synced) VALUES (1, 0, 0); "
            "UPDATE core_rollupstate SET mutations = mutations + 1 WHERE id = 1; END"
        )
    apps.get_model("core", "RollupState").objects.update_or_create(pk=1, defaults={"mutations": 1, "synced": 0})


def remove(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    for name in TRIGGERS:
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_camera_events'),
    ]

    operations = [
        migrations.CreateModel(
            name='RollupState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mutations', models.BigIntegerField(default=0)),
                ('synced', models.BigIntegerField(default=0)),
                ('horizon', models.DateTimeField(null=True)),
                ('rebuilt', models.DateTimeField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='event',
            name='uid',
            field=models.CharField(default=None, max_length=64, null=True, unique=True),
        ),
        migrations.CreateModel(
            name='DayCount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField()),
                ('sector', models.CharField(max_length=50)),
                ('fruit_type', models.CharField(max_length=20)),
                ('is_good', models.BooleanField()),
                ('deformity_type', models.CharField(blank=True, default='', max_length=50)),
                ('is_demo', models.BooleanField(default=False)),
                ('n', models.IntegerField(default=0)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('day', 'sector', 'fruit_type', 'is_good', 'deformity_type', 'is_demo'), name='day_count_key')],
            },
        ),
        migrations.CreateModel(
            name='MinuteStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('camera', models.CharField(max_length=40)),
                ('minute', models.DateTimeField()),
                ('lot', models.CharField(blank=True, max_length=40)),
                ('is_demo', models.BooleanField(default=False)),
                ('boa', models.IntegerField(default=0)),
                ('baixa_qualidade', models.IntegerField(default=0)),
                ('podre', models.IntegerField(default=0)),
                ('revisar', models.IntegerField(default=0)),
                ('sizes', models.JSONField(default=dict)),
                ('first', models.DateTimeField()),
                ('last', models.DateTimeField()),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('camera', 'minute', 'lot', 'is_demo'), name='minute_stat_key')],
            },
        ),
        migrations.RunPython(install, remove),
    ]

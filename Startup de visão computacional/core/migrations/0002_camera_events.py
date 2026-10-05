from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='camera',
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
        migrations.AddField(
            model_name='event',
            name='decided_by',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='event',
            name='label',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='event',
            name='lot',
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
        migrations.AddField(
            model_name='event',
            name='model_version',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='event',
            name='needs_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='event',
            name='size_mm',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='source',
            field=models.CharField(db_index=True, default='foto', max_length=10),
        ),
        migrations.AddField(
            model_name='event',
            name='track_id',
            field=models.IntegerField(null=True),
        ),
    ]

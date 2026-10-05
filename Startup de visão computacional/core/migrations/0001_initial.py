import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('sector', models.CharField(db_index=True, max_length=50)),
                ('fruit_type', models.CharField(max_length=20)),
                ('is_good', models.BooleanField()),
                ('deformity_type', models.CharField(blank=True, max_length=50, null=True)),
                ('confidence', models.FloatField(null=True)),
                ('is_demo', models.BooleanField(db_index=True, default=False)),
                ('image', models.CharField(blank=True, max_length=64)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

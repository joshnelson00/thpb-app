# Generated by Django 5.1.5 on 2025-05-11 21:38

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website_app', '0017_eventsubstitution'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubstitutionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='substitution_requests', to='website_app.event')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='substitution_requests', to='website_app.group')),
                ('requesting_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='substitution_requests_made', to=settings.AUTH_USER_MODEL)),
                ('target_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='substitution_requests_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'SubstitutionRequest',
                'unique_together': {('event', 'requesting_user', 'target_user', 'group')},
            },
        ),
    ]

# Generated by Django 4.2.6 on 2023-10-17 08:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0003_remove_matchresult_total_points'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournament',
            name='no_of_group',
            field=models.PositiveIntegerField(default=3),
            preserve_default=False,
        ),
    ]
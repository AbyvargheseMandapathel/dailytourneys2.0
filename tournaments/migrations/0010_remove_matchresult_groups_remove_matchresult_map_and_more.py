# Generated by Django 4.2.6 on 2023-10-17 10:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0009_matchresult_winning_team'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='matchresult',
            name='groups',
        ),
        migrations.RemoveField(
            model_name='matchresult',
            name='map',
        ),
        migrations.CreateModel(
            name='MatchSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('map', models.CharField(max_length=255)),
                ('groups', models.ManyToManyField(blank=True, related_name='scheduled_matches', to='tournaments.group')),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tournaments.tournament')),
            ],
        ),
        migrations.AddField(
            model_name='matchresult',
            name='match_schedule',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='tournaments.matchschedule'),
            preserve_default=False,
        ),
    ]
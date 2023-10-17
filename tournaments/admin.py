from django.contrib import admin
from .models import Tournament , Team,MatchResult ,Group,MatchSchedule,OverallStandings

# Register your models here.

admin.site.register(Team)
admin.site.register(Tournament)
admin.site.register(MatchResult)
admin.site.register(Group)
admin.site.register(MatchSchedule)
admin.site.register(OverallStandings)
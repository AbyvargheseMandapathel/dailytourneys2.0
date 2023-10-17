from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver


class Team(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='team_logos/')

    def __str__(self):
        return self.name
    
    
class Tournament(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Foreign key to link each tournament to a user
    name = models.CharField(max_length=255)
    no_of_teams = models.PositiveIntegerField()
    no_of_matches = models.PositiveIntegerField()
    no_of_group = models.PositiveIntegerField()
    no_of_teams_per_group = models.PositiveIntegerField()
    teams = models.ManyToManyField(Team, related_name='tournaments', blank=True)

    def __str__(self):
        return self.name
    
class Group(models.Model):
    name = models.CharField(max_length=1)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    teams = models.ManyToManyField(Team, related_name='groups', blank=True)

    def __str__(self):
        return f"{self.tournament.name} - Group {self.name}"

class MatchSchedule(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    map = models.CharField(max_length=255)
    match_number = models.PositiveIntegerField()  # New field for match numbering
    groups = models.ManyToManyField(Group, related_name='scheduled_matches', blank=True)
    winning_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='match_wins'
    )

    def __str__(self):
        return f"{self.tournament.name} - Map: {self.map} - Match {self.match_number}"

    
class MatchResult(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    match_schedule = models.ForeignKey(MatchSchedule, on_delete=models.CASCADE, related_name='matches')
    finishes_points = models.PositiveIntegerField()
    position_points = models.PositiveIntegerField()

    def calculate_total_points(self):
        return self.finishes_points + self.position_points

    total_points = property(calculate_total_points)

    def __str__(self):
        return f"{self.tournament.name} - Match {self.match_schedule.match_number} - {self.team.name}"
    
class OverallStandings(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    total_position_points = models.PositiveIntegerField(default=0)
    total_finishes_points = models.PositiveIntegerField(default=0)
    total_wins = models.PositiveIntegerField(default=0)
    total_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.tournament.name} - {self.team.name} Standings"

@receiver(post_save, sender=MatchResult)
def update_overall_standings_on_match_result_save(sender, instance, **kwargs):
    # Update OverallStandings whenever a MatchResult is added or updated
    overall_standings, created = OverallStandings.objects.get_or_create(
        team=instance.team,
        tournament=instance.tournament
    )
    match_results = MatchResult.objects.filter(team=instance.team, tournament=instance.tournament)
    wins = match_results.filter(match_schedule__winning_team=instance.team).count()
    overall_standings.total_wins = wins
    overall_standings.total_position_points = match_results.aggregate(
        total_position_points=Sum('position_points')
    )['total_position_points'] or 0
    overall_standings.total_finishes_points = match_results.aggregate(
        total_finishes_points=Sum('finishes_points')
    )['total_finishes_points'] or 0
    overall_standings.total_points = overall_standings.total_position_points + overall_standings.total_finishes_points
    overall_standings.save()

@receiver(pre_delete, sender=MatchResult)
def update_overall_standings_on_match_result_delete(sender, instance, **kwargs):
    # Subtract points when a MatchResult is deleted
    overall_standings, created = OverallStandings.objects.get_or_create(
        team=instance.team,
        tournament=instance.tournament
    )
    overall_standings.total_wins -= 1 if instance.match_schedule.winning_team == instance.team else 0
    overall_standings.total_position_points -= instance.position_points
    overall_standings.total_finishes_points -= instance.finishes_points
    overall_standings.total_points = overall_standings.total_position_points + overall_standings.total_finishes_points
    overall_standings.save()

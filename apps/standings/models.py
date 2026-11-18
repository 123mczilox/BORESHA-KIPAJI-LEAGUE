from django.db import models
from django.db.models import Q, F

# Create your models here.

class TeamStandings(models.Model):
    session = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='standings'
    )
    team = models.ForeignKey(
        'teams.Team',
        on_delete=models.PROTECT,
        related_name='session_standings'
    )
    played = models.PositiveIntegerField(default=0)
    won = models.PositiveIntegerField(default=0)
    drawn = models.PositiveIntegerField(default=0)
    lost = models.PositiveIntegerField(default=0)

    goals_for = models.PositiveIntegerField(default=0)
    goals_against = models.PositiveIntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-points']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'team'],
                name='unique_team_standings_per_session'
            ),
            models.CheckConstraint(
                condition=Q(played=F('won') + F('drawn') + F('lost')),
                name='standing_played_matches_consistent'
            )
        ]

    @property
    def goal_difference_value(self):
        return self.goals_for - self.goals_against

    def __str__(self):
        return f"{self.team.name}-{self.session}"


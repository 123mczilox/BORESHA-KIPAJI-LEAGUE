from django.db import models
from django.db.models import Q, F
from apps.teams.models import Team


class Season(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    year = models.PositiveIntegerField(
        unique=True
    )

    start_date = models.DateField()

    end_date = models.DateField()

    is_active = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-year']

        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F('start_date')),
                name='season_end_after_start'
            ),
            models.UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True),
                name='only_one_active_season'
            ),
        ]

    def __str__(self):
        return self.name

class Match(models.Model):

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        LIVE = 'live', 'Live'
        COMPLETED = 'completed', 'Completed'
        POSTPONED = 'postponed', 'Postponed'
        CANCELLED = 'cancelled', 'Cancelled'

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='matches'
    )

    home_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name='home_matches'
    )

    away_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name='away_matches'
    )

    matchweek = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    kickoff_time = models.DateTimeField()

    venue = models.CharField(
        max_length=150,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )

    home_score = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    away_score = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['kickoff_time']

        constraints = [
            models.CheckConstraint(
                condition=~Q(home_team=F('away_team')),
                name='match_teams_must_be_different'
            ),
        ]

    def __str__(self):
        return f'{self.home_team} vs {self.away_team}'    

class MatchOfficial(models.Model):

    class Role(models.TextChoices):
        REFEREE = 'referee', 'Referee'
        ASSISTANT_REFEREE = 'assistant', 'Assistant Referee'
        FOURTH_OFFICIAL = 'fourth', 'Fourth Official'

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='officials'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='officiated_matches'
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'user'],
                name='unique_official_per_match'
            )
        ]

    def __str__(self):
        return f'{self.user.username} - {self.match}'


class MatchEvent(models.Model):

    class EventType(models.TextChoices):
        GOAL = 'goal', 'Goal'
        OWN_GOAL = 'own_goal', 'Own Goal'
        PENALTY_GOAL = 'penalty_goal', 'Penalty Goal'
        YELLOW_CARD = 'yellow_card', 'Yellow Card'
        RED_CARD = 'red_card', 'Red Card'
        SUBSTITUTION = 'substitution', 'Substitution'

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='events'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices
    )

    player = models.ForeignKey(
        'Players.Player',
        on_delete=models.PROTECT,
        related_name='match_events'
    )

    related_player = models.ForeignKey(
        'Players.Player',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='related_match_events'
    )

    minute = models.PositiveSmallIntegerField()

    added_time = models.PositiveSmallIntegerField(
        default=0
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f'{self.event_type} - {self.player} ({self.match})'    
    
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

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


class SeasonTeam(models.Model):
    season = models.ForeignKey(
        Season,
        on_delete=models.PROTECT,
        related_name='team_memberships',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name='season_memberships',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['season', 'team']
        constraints = [
            models.UniqueConstraint(
                fields=['season', 'team'],
                name='unique_team_per_season',
            ),
        ]

    def clean(self):
        super().clean()
        if self.team_id and not self.team.is_active:
            raise ValidationError({
                'team': 'Inactive teams cannot be added to a season.'
            })

    def __str__(self):
        return f'{self.team} - {self.season}'


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

    started_at = models.DateTimeField(
        null=True,
        blank=True,
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

    def clean(self):
        super().clean()
        errors = {}

        if self.home_team_id and self.away_team_id:
            if self.home_team_id == self.away_team_id:
                errors['away_team'] = 'Home and away teams must be different.'

        if self.matchweek is not None and self.matchweek < 1:
            errors['matchweek'] = 'Matchweek must be a positive number.'

        if self.season_id and self.kickoff_time:
            kickoff_date = timezone.localtime(self.kickoff_time).date()
            if not self.season.start_date <= kickoff_date <= self.season.end_date:
                errors['kickoff_time'] = (
                    'Kickoff must fall within the selected season dates.'
                )

        if self.season_id and self.home_team_id and self.away_team_id:
            active_teams = Team.objects.filter(
                pk__in=(self.home_team_id, self.away_team_id),
                is_active=True,
            ).count()
            if active_teams != 2:
                errors['home_team'] = (
                    'Fixtures can only include active teams.'
                )
            memberships = SeasonTeam.objects.filter(
                season_id=self.season_id,
                team_id__in=(self.home_team_id, self.away_team_id),
            ).count()
            if memberships != 2:
                errors['season'] = (
                    'Both teams must be registered for the selected season.'
                )

        if (self.home_score is None) != (self.away_score is None):
            errors['home_score'] = (
                'Home and away scores must either both be set or both be empty.'
            )

        if (
            self.status == self.Status.COMPLETED
            and (self.home_score is None or self.away_score is None)
        ):
            errors['status'] = 'Completed matches must have a result.'

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.home_team} vs {self.away_team}'


class MatchOfficial(models.Model):

    class Role(models.TextChoices):
        REFEREE = 'referee', 'Referee'
        ASSISTANT_REFEREE = 'assistant', 'Assistant Referee'
        FOURTH_OFFICIAL = 'fourth', 'Fourth Official'

    match = models.ForeignKey(
        Match,
        on_delete=models.PROTECT,
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

    def clean(self):
        super().clean()
        if self.user_id:
            from apps.accounts.permissions import is_match_official

            if not is_match_official(self.user):
                raise ValidationError({
                    'user': (
                        'Only users with the Match Official role can be assigned.'
                    )
                })

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
        on_delete=models.PROTECT,
        related_name='events'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices
    )

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='match_events'
    )

    related_player = models.ForeignKey(
        'players.Player',
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

    def team_for_player(self, player_id):
        match_date = timezone.localtime(self.match.kickoff_time).date()
        return list(
            self.match.season.player_registrations.filter(
                player_id=player_id,
                team_id__in=(self.match.home_team_id, self.match.away_team_id),
                start_date__lte=match_date,
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=match_date)
            ).values_list('team_id', flat=True).distinct()
        )

    def clean(self):
        super().clean()
        if not self.match_id or not self.player_id:
            return

        errors = {}
        if self.minute is not None and self.minute < 1:
            errors['minute'] = 'Event minute must be at least 1.'

        if self.match.status not in (
            Match.Status.LIVE,
            Match.Status.COMPLETED,
        ):
            errors['match'] = (
                'Events can only be recorded for live or completed matches.'
            )

        duplicate_events = MatchEvent.objects.filter(
            match_id=self.match_id,
            event_type=self.event_type,
            player_id=self.player_id,
            related_player_id=self.related_player_id,
            minute=self.minute,
            added_time=self.added_time,
        )
        if self.pk:
            duplicate_events = duplicate_events.exclude(pk=self.pk)
        if duplicate_events.exists():
            errors['minute'] = 'This match event has already been recorded.'

        player_teams = self.team_for_player(self.player_id)
        if len(player_teams) != 1:
            errors['player'] = (
                'The player must be registered to exactly one participating '
                'team on the match date.'
            )

        if self.event_type == self.EventType.SUBSTITUTION:
            if not self.related_player_id:
                errors['related_player'] = (
                    'A substitution requires the player entering the match.'
                )
            elif self.related_player_id == self.player_id:
                errors['related_player'] = (
                    'The outgoing and incoming players must be different.'
                )
            else:
                related_teams = self.team_for_player(self.related_player_id)
                if (
                    len(player_teams) != 1
                    or len(related_teams) != 1
                    or player_teams[0] != related_teams[0]
                ):
                    errors['related_player'] = (
                        'Both substitution players must be registered to the '
                        'same participating team on the match date.'
                    )
        elif self.related_player_id:
            errors['related_player'] = (
                'A related player is only valid for a substitution.'
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.event_type} - {self.player} ({self.match})'
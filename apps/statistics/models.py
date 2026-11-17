from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class PlayerMatchPerformance(models.Model):
    """
    Records one player's verified performance in a particular match.
    """

    match = models.ForeignKey(
        'matches.Match',
        on_delete=models.PROTECT,
        related_name='player_performances'
    )

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='match_performances'
    )

    minutes_played = models.PositiveIntegerField(default=0)

    goals_scored = models.PositiveIntegerField(default=0)

    assists = models.PositiveIntegerField(default=0)

    clean_sheet = models.BooleanField(default=False)

    penalties_saved = models.PositiveIntegerField(default=0)

    yellow_cards = models.PositiveIntegerField(default=0)

    red_cards = models.PositiveIntegerField(default=0)

    own_goals = models.PositiveIntegerField(default=0)

    player_of_the_match = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-goals_scored', '-assists']

        constraints = [
            models.UniqueConstraint(
                fields=['match', 'player'],
                name='unique_player_per_match_performance'
            )
        ]

    def clean(self):
        super().clean()

        if not self.match_id or not self.player_id:
            return

        match_date = timezone.localtime(
            self.match.kickoff_time
        ).date()

        eligible_teams = [
            self.match.home_team_id,
            self.match.away_team_id
        ]

        registration_exists = self.player.registrations.filter(
            season=self.match.season,
            team_id__in=eligible_teams,
            start_date__lte=match_date
        ).filter(
            models.Q(end_date__isnull=True)
            | models.Q(end_date__gte=match_date)
        ).exists()

        if not registration_exists:
            raise ValidationError({
                'player': (
                    'This player was not registered to either '
                    'team for this match on the match date.'
                )
            })

    def __str__(self):
        return f'{self.player} - {self.match}'


class PlayerSeasonStatistics(models.Model):
    """
    Stores a player's accumulated statistics for an entire season.
    """

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='season_statistics'
    )

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='player_statistics'
    )

    appearances = models.PositiveIntegerField(default=0)

    clean_sheets = models.PositiveIntegerField(default=0)

    penalties_saved = models.PositiveIntegerField(default=0)

    player_of_the_match = models.PositiveIntegerField(default=0)

    goals_scored = models.PositiveIntegerField(default=0)

    assists = models.PositiveIntegerField(default=0)

    yellow_cards = models.PositiveIntegerField(default=0)

    red_cards = models.PositiveIntegerField(default=0)

    own_goals = models.PositiveIntegerField(default=0)

    minutes_played = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-goals_scored', '-assists']

        constraints = [
            models.UniqueConstraint(
                fields=['player', 'season'],
                name='unique_player_statistics_per_season'
            )
        ]

    def __str__(self):
        return f'{self.player} - {self.season}'
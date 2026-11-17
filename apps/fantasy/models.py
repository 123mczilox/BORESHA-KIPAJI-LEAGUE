from django.db import models
from django.conf import settings
from django.db.models import Q, F


class FantasyTeam(models.Model):
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fantasy_teams'
    )

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='fantasy_teams'
    )

    name = models.CharField(max_length=100)

    budget_remaining = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    total_points = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_points', 'name']

        constraints = [
            models.UniqueConstraint(
                fields=['manager', 'season'],
                name='unique_fantasy_team_per_manager_season'
            ),

            models.UniqueConstraint(
                fields=['season', 'name'],
                name='unique_fantasy_team_name_per_season'
            ),

            models.CheckConstraint(
                condition=Q(budget_remaining__gte=0),
                name='fantasy_budget_cannot_be_negative'
            )
        ]

    def __str__(self):
        return f'{self.name} - {self.manager.username} - {self.season}'


class FantasyPlayerSelection(models.Model):

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name='player_selections'
    )

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='fantasy_selections'
    )

    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_captain = models.BooleanField(default=False)

    is_vice_captain = models.BooleanField(default=False)

    is_starting = models.BooleanField(default=False)

    selected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['fantasy_team', 'player'],
                name='unique_player_selection_per_fantasy_team'
            ),

            models.CheckConstraint(
                condition=~(
                    Q(is_captain=True) &
                    Q(is_vice_captain=True)
                ),
                name='player_cannot_be_captain_and_vice'
            ),

            models.UniqueConstraint(
                fields=['fantasy_team'],
                condition=Q(is_captain=True),
                name='one_captain_per_fantasy_team'
            ),

            models.UniqueConstraint(
                fields=['fantasy_team'],
                condition=Q(is_vice_captain=True),
                name='one_vice_captain_per_fantasy_team'
            )
        ]

    def __str__(self):
        return f'{self.player} - {self.fantasy_team.name}'


class FantasyGameWeek(models.Model):

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='fantasy_game_weeks'
    )

    number = models.PositiveIntegerField()

    name = models.CharField(
        max_length=100,
        blank=True
    )

    deadline = models.DateTimeField()

    is_current = models.BooleanField(default=False)

    is_finished = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']

        constraints = [
            models.UniqueConstraint(
                fields=['season', 'number'],
                name='unique_game_week_per_season'
            ),

            models.UniqueConstraint(
                fields=['season'],
                condition=Q(is_current=True),
                name='only_one_current_game_week_per_season'
            )
        ]

    def __str__(self):
        return f'Game Week {self.number} - {self.season.name}'


class FantasyGameweekMatch(models.Model):
    """
    Connects real league fixtures to fantasy gameweeks.
    A real match can only belong to one fantasy gameweek.
    """

    gameweek = models.ForeignKey(
        FantasyGameWeek,
        on_delete=models.CASCADE,
        related_name='scheduled_matches'
    )

    match = models.ForeignKey(
        'matches.Match',
        on_delete=models.PROTECT,
        related_name='fantasy_gameweek_links'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['gameweek', 'match'],
                name='unique_match_per_fantasy_gameweek'
            ),

            models.UniqueConstraint(
                fields=['match'],
                name='match_assigned_to_one_fantasy_gameweek'
            )
        ]

    def __str__(self):
        return f'{self.match} - {self.gameweek}'


class PlayerFantasyValue(models.Model):

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='fantasy_values'
    )

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='player_fantasy_values'
    )

    initial_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'season'],
                name='unique_player_fantasy_value_per_season'
            ),

            models.CheckConstraint(
                condition=Q(initial_price__gt=0),
                name='fantasy_initial_price_positive'
            ),

            models.CheckConstraint(
                condition=Q(current_price__gt=0),
                name='fantasy_current_price_positive'
            )
        ]

    def __str__(self):
        return f'{self.player} - {self.season.name} - {self.current_price}'


class FantasyTransfer(models.Model):

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name='transfers'
    )

    game_week = models.ForeignKey(
        FantasyGameWeek,
        on_delete=models.PROTECT,
        related_name='transfers'
    )

    player_in = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='transfers_in'
    )

    player_out = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='transfers_out'
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    points_cost = models.PositiveIntegerField(default=0)

    transfer_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transfer_date']

        constraints = [
            models.CheckConstraint(
                condition=~Q(player_out=F('player_in')),
                name='transfer_players_must_be_different'
            )
        ]

    def __str__(self):
        return (
            f'{self.fantasy_team.name}: '
            f'{self.player_out} -> {self.player_in} '
            f'(GW{self.game_week.number})'
        )


class FantasyScoringRule(models.Model):

    class EventType(models.TextChoices):
        APPEARANCE = 'APPEARANCE', 'Appearance'
        GOAL = 'GOAL', 'Goal'
        ASSIST = 'ASSIST', 'Assist'
        CLEAN_SHEET = 'CLEAN_SHEET', 'Clean Sheet'
        PENALTY_SAVE = 'PENALTY_SAVE', 'Penalty Save'
        YELLOW_CARD = 'YELLOW_CARD', 'Yellow Card'
        RED_CARD = 'RED_CARD', 'Red Card'
        OWN_GOAL = 'OWN_GOAL', 'Own Goal'
        PLAYER_OF_MATCH = 'PLAYER_OF_MATCH', 'Player of the Match'

    class Position(models.TextChoices):
        ALL = 'ALL', 'All Positions'
        GOALKEEPER = 'GK', 'Goalkeeper'
        DEFENDER = 'DEF', 'Defender'
        MIDFIELDER = 'MID', 'Midfielder'
        FORWARD = 'FWD', 'Forward'

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='fantasy_scoring_rules'
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices
    )

    position = models.CharField(
        max_length=3,
        choices=Position.choices,
        default=Position.ALL
    )

    points = models.IntegerField()

    description = models.CharField(
        max_length=255,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['season', 'event_type', 'position'],
                name='unique_fantasy_rule_per_season_event_position'
            )
        ]

    def __str__(self):
        return f'{self.event_type} ({self.position}): {self.points} pts'


class PlayerGameweekScore(models.Model):

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='fantasy_gameweek_scores'
    )

    gameweek = models.ForeignKey(
        FantasyGameWeek,
        on_delete=models.PROTECT,
        related_name='player_scores'
    )

    minutes_played = models.PositiveIntegerField(default=0)

    points = models.IntegerField(default=0)

    scoring_breakdown = models.JSONField(
        default=dict,
        blank=True
    )

    is_final = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'gameweek'],
                name='unique_player_score_per_gameweek'
            )
        ]

    def __str__(self):
        return f'{self.player} - GW{self.gameweek.number}: {self.points}'


class FantasyGameweekScore(models.Model):

    fantasy_team = models.ForeignKey(
        FantasyTeam,
        on_delete=models.CASCADE,
        related_name='gameweek_scores'
    )

    gameweek = models.ForeignKey(
        FantasyGameWeek,
        on_delete=models.PROTECT,
        related_name='fantasy_team_scores'
    )

    points_earned = models.IntegerField(default=0)

    transfer_points_cost = models.PositiveIntegerField(default=0)

    total_points = models.IntegerField(default=0)

    rank = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_points']

        constraints = [
            models.UniqueConstraint(
                fields=['fantasy_team', 'gameweek'],
                name='unique_fantasy_team_score_per_gameweek'
            )
        ]

    def __str__(self):
        return (
            f'{self.fantasy_team.name} - '
            f'GW{self.gameweek.number}: {self.total_points}'
        )
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings


class Player(models.Model):

    class Position(models.TextChoices):
        GOALKEEPER = 'GK', 'Goalkeeper'
        DEFENDER = 'DEF', 'Defender'
        MIDFIELDER = 'MID', 'Midfielder'
        FORWARD = 'FWD', 'Forward'

    first_name = models.CharField(max_length=100)

    last_name = models.CharField(max_length=100)

    date_of_birth = models.DateField()

    position = models.CharField(
        max_length=3,
        choices=Position.choices
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']

    def clean(self):
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError({
                'date_of_birth': 'Date of birth cannot be in the future.'
            })

    @property
    def age(self):
        today = timezone.now().date()
        return (
            today.year - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class PlayerRegistration(models.Model):

    player = models.ForeignKey(
        'players.Player',
        on_delete=models.PROTECT,
        related_name='registrations'
    )

    team = models.ForeignKey(
        'teams.Team',
        on_delete=models.PROTECT,
        related_name='player_registrations'
    )

    season = models.ForeignKey(
        'matches.Season',
        on_delete=models.PROTECT,
        related_name='player_registrations'
    )

    shirt_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['team', 'shirt_number']

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(end_date__gte=models.F('start_date'))
                ),
                name='registration_valid_date_range'
            ),

            models.UniqueConstraint(
                fields=['player', 'season'],
                condition=models.Q(end_date__isnull=True),
                name='unique_current_player_season'
            ),

            models.UniqueConstraint(
                fields=['team', 'season', 'shirt_number'],
                condition=(
                    models.Q(end_date__isnull=True)
                    & models.Q(shirt_number__isnull=False)
                ),
                name='unique_current_team_shirt'
            ),
        ]

    def __str__(self):
        return (
            f'{self.player} - {self.team} '
            f'({self.season})'
        )
        
    def clean(self):
        super().clean()

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'End date cannot be earlier than start date.'
            })

        overlapping = PlayerRegistration.objects.filter(
            player=self.player,
            season=self.season
        ).exclude(pk=self.pk).filter(
            models.Q(end_date__isnull=True)
            | models.Q(end_date__gte=self.start_date)
        )

        if self.end_date:
            overlapping = overlapping.filter(
                start_date__lte=self.end_date
            )

        if overlapping.exists():
            raise ValidationError({
                'player': (
                    'This player already has a registration '
                    'that overlaps with these dates.'
                )
            })    
    
    
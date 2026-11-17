from django.db import models
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone


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
        super().clean()

        if (
            self.date_of_birth
            and self.date_of_birth > timezone.now().date()
        ):
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

            models.CheckConstraint(
                condition=(
                    models.Q(shirt_number__isnull=True)
                    | models.Q(shirt_number__gt=0)
                ),
                name='registration_shirt_number_positive'
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

    def clean(self):
        super().clean()

        if (
            not self.player_id
            or not self.team_id
            or not self.season_id
            or not self.start_date
        ):
            return

        try:
            season = self.season
        except ObjectDoesNotExist:
            return

        errors = {}

        # Validate registration dates against the season.
        if self.start_date < season.start_date:
            errors['start_date'] = (
                'Registration cannot start before the season begins.'
            )

        if self.start_date > season.end_date:
            errors['start_date'] = (
                'Registration cannot start after the season ends.'
            )

        if self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = (
                    'End date cannot be earlier than start date.'
                )

            if self.end_date > season.end_date:
                errors['end_date'] = (
                    'Registration cannot end after the season ends.'
                )

        if errors:
            raise ValidationError(errors)

        effective_end_date = self.end_date or season.end_date
        overlapping_player_registrations = (
            PlayerRegistration.objects.filter(player_id=self.player_id)
            .exclude(pk=self.pk)
            .filter(start_date__lte=effective_end_date)
            .filter(
                models.Q(
                    end_date__isnull=True,
                    season__end_date__gte=self.start_date,
                )
                | models.Q(end_date__gte=self.start_date)
            )
        )

        if overlapping_player_registrations.exists():
            raise ValidationError({
                'player': (
                    'This player already has a registration that overlaps '
                    'these dates, including in another season.'
                )
            })

        if self.shirt_number:
            overlapping_shirt_numbers = PlayerRegistration.objects.filter(
                team_id=self.team_id,
                season_id=self.season_id,
                shirt_number=self.shirt_number,
                start_date__lte=effective_end_date,
            ).exclude(pk=self.pk).filter(
                models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=self.start_date)
            )

            if overlapping_shirt_numbers.exists():
                raise ValidationError({
                    'shirt_number': (
                        'This shirt number is already assigned to another '
                        'player during these dates.'
                    )
                })

    def __str__(self):
        return f'{self.player} - {self.team} ({self.season})'
from django.core.exceptions import ValidationError
from django.db import models


class Sponsor(models.Model):

    class Level(models.TextChoices):
        TITLE = 'title', 'Title'
        PLATINUM = 'platinum', 'Platinum'
        GOLD = 'gold', 'Gold'
        SILVER = 'silver', 'Silver'
        BRONZE = 'bronze', 'Bronze'
        COMMUNITY = 'community', 'Community'

    name = models.CharField(max_length=150, unique=True)
    logo = models.ImageField(
        upload_to='sponsors/',
        blank=True
    )
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.COMMUNITY
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    partnership_start_date = models.DateField(null=True, blank=True)
    partnership_end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(partnership_end_date__isnull=True)
                    | (
                        models.Q(partnership_start_date__isnull=False)
                        & models.Q(
                            partnership_end_date__gte=models.F(
                                'partnership_start_date'
                            )
                        )
                    )
                ),
                name='sponsor_valid_partnership_dates'
            ),
        ]
        indexes = [
            models.Index(
                fields=['is_active', 'display_order'],
                name='sponsor_active_order_idx'
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.partnership_end_date
            and (
                not self.partnership_start_date
                or self.partnership_end_date < self.partnership_start_date
            )
        ):
            raise ValidationError({
                'partnership_end_date': (
                    'Partnership end date requires a start date and cannot '
                    'be before it.'
                )
            })

    def __str__(self):
        return self.name

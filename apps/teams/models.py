from django.db import models
from django.conf import settings
# Create your models here.



class Team(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    short_name = models.CharField(
        max_length=10,
        blank=True
    )

    county = models.CharField(
        max_length=100,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    founded_year = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


class TeamManagerAssignment(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_assignments'
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='manager_assignments'
    )

    is_active = models.BooleanField(
        default=True
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'team'],
                name='unique_team_manager_assignment'
            )
        ]

    def __str__(self):
        return f'{self.user.username} - {self.team.name}'
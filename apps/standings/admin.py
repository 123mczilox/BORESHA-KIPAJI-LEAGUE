from django.contrib import admin

from apps.accounts.permissions import is_league_admin

from .models import TeamStandings


@admin.register(TeamStandings)
class TeamStandingsAdmin(admin.ModelAdmin):

    list_display = (
        'team',
        'session',
        'played',
        'won',
        'drawn',
        'lost',
        'goals_for',
        'goals_against',
        'goal_difference',
        'points',
        'updated_at',
    )

    list_filter = (
        'session',
        'team',
    )

    search_fields = (
        'team__name',
        'session__name',
    )

    list_select_related = (
        'team',
        'session',
    )

    ordering = (
        'session',
        '-points',
    )

    readonly_fields = (
        'team',
        'session',
        'played',
        'won',
        'drawn',
        'lost',
        'goals_for',
        'goals_against',
        'goal_difference',
        'points',
        'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return (
            super().has_view_permission(request)
            and is_league_admin(request.user)
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
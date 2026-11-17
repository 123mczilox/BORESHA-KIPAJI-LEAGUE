from django.contrib import admin
from django.db import models

from apps.accounts.permissions import (
    can_manage_match,
    can_view_match,
    is_league_admin,
    is_match_official,
    is_team_manager,
    visible_players_for_user,
)

from apps.matches.models import Match
from .models import PlayerMatchPerformance, PlayerSeasonStatistics


@admin.register(PlayerMatchPerformance)
class PlayerMatchPerformanceAdmin(admin.ModelAdmin):

    list_display = (
        'player',
        'match',
        'minutes_played',
        'goals_scored',
        'assists',
        'clean_sheet',
        'penalties_saved',
        'yellow_cards',
        'red_cards',
        'player_of_the_match',
    )

    list_filter = (
        'match__season',
        'clean_sheet',
        'player_of_the_match',
    )

    search_fields = (
        'player__first_name',
        'player__last_name',
        'match__home_team__name',
        'match__away_team__name',
    )

    list_select_related = (
        'player',
        'match',
        'match__season',
    )

    ordering = (
        '-goals_scored',
        '-assists',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_league_admin(request.user):
            return queryset

        if is_match_official(request.user):
            return queryset.filter(
                match__officials__user=request.user
            ).distinct()

        if is_team_manager(request.user):
            return queryset.filter(
                models.Q(
                    match__home_team__manager_assignments__user=request.user,
                    match__home_team__manager_assignments__is_active=True,
                )
                | models.Q(
                    match__away_team__manager_assignments__user=request.user,
                    match__away_team__manager_assignments__is_active=True,
                )
            ).distinct()

        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_match_official(request.user)
                or is_team_manager(request.user)
            )

        return can_view_match(request.user, obj.match)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and (
                is_league_admin(request.user)
                or is_match_official(request.user)
            )
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_match_official(request.user)
            )

        return can_manage_match(request.user, obj.match)

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request)
            and is_league_admin(request.user)
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'match' and is_match_official(request.user):
            kwargs['queryset'] = Match.objects.filter(
                officials__user=request.user
            )
        elif db_field.name == 'player':
            kwargs['queryset'] = visible_players_for_user(request.user)

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )


@admin.register(PlayerSeasonStatistics)
class PlayerSeasonStatisticsAdmin(admin.ModelAdmin):

    list_display = (
        'player',
        'season',
        'appearances',
        'goals_scored',
        'assists',
        'clean_sheets',
        'own_goals',
        'minutes_played',
    )

    list_filter = (
        'season',
    )

    search_fields = (
        'player__first_name',
        'player__last_name',
        'season__name',
    )

    list_select_related = (
        'player',
        'season',
    )

    ordering = (
        '-goals_scored',
        '-assists',
    )

    readonly_fields = (
        'player',
        'season',
        'appearances',
        'goals_scored',
        'assists',
        'clean_sheets',
        'penalties_saved',
        'player_of_the_match',
        'yellow_cards',
        'red_cards',
        'own_goals',
        'minutes_played',
        'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_league_admin(request.user):
            return queryset

        if is_team_manager(request.user):
            return queryset.filter(
                player__registrations__season=models.F('season'),
                player__registrations__team__manager_assignments__user=request.user,
                player__registrations__team__manager_assignments__is_active=True,
            ).distinct()

        if is_match_official(request.user):
            assigned_team_matches = (
                models.Q(
                    player__registrations__team__home_matches__season=models.F(
                        'season'
                    ),
                    player__registrations__team__home_matches__officials__user=request.user,
                )
                | models.Q(
                    player__registrations__team__away_matches__season=models.F(
                        'season'
                    ),
                    player__registrations__team__away_matches__officials__user=request.user,
                )
            )
            return queryset.filter(
                assigned_team_matches,
                player__registrations__season=models.F('season'),
            ).distinct()

        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_match_official(request.user)
                or is_team_manager(request.user)
            )

        return self.get_queryset(request).filter(pk=obj.pk).exists()
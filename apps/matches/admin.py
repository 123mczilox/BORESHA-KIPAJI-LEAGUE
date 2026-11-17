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

from .models import Season, Match, MatchOfficial, MatchEvent


class MatchOfficialInline(admin.TabularInline):
    model = MatchOfficial
    extra = 1

    def has_view_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_add_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0

    def has_view_permission(self, request, obj=None):
        return (
            obj is not None
            and (
                is_league_admin(request.user)
                or can_manage_match(request.user, obj)
            )
        )

    def has_add_permission(self, request, obj=None):
        return obj is not None and can_manage_match(request.user, obj)

    def has_change_permission(self, request, obj=None):
        return obj is not None and can_manage_match(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'year',
        'start_date',
        'end_date',
        'is_active',
    )

    list_filter = ('is_active', 'year')
    search_fields = ('name',)
    ordering = ('-year',)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and is_league_admin(
            request.user
        )

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(
            request,
        ) and is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(
            request,
        ) and is_league_admin(request.user)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        'home_team',
        'away_team',
        'season',
        'matchweek',
        'kickoff_time',
        'status',
        'home_score',
        'away_score',
    )

    list_filter = (
        'season',
        'status',
        'matchweek',
    )

    search_fields = (
        'home_team__name',
        'away_team__name',
        'venue',
    )

    date_hierarchy = 'kickoff_time'

    list_select_related = (
        'season',
        'home_team',
        'away_team',
    )

    inlines = [
        MatchOfficialInline,
        MatchEventInline,
    ]

    ordering = ('kickoff_time',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_league_admin(request.user):
            return queryset

        if is_match_official(request.user):
            return queryset.filter(officials__user=request.user).distinct()

        if is_team_manager(request.user):
            return queryset.filter(
                models.Q(
                    home_team__manager_assignments__user=request.user,
                    home_team__manager_assignments__is_active=True,
                )
                | models.Q(
                    away_team__manager_assignments__user=request.user,
                    away_team__manager_assignments__is_active=True,
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

        return can_view_match(request.user, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and is_league_admin(
            request.user
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_match_official(request.user)
            )

        return can_manage_match(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(
            request,
        ) and is_league_admin(request.user)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and can_manage_match(request.user, obj) and (
            not is_league_admin(request.user)
        ):
            return (
                'season',
                'home_team',
                'away_team',
                'matchweek',
                'kickoff_time',
                'venue',
            )

        return super().get_readonly_fields(request, obj)


@admin.register(MatchOfficial)
class MatchOfficialAdmin(admin.ModelAdmin):
    list_display = (
        'match',
        'user',
        'role',
    )

    list_filter = ('role',)
    search_fields = ('user__username',)
    list_select_related = ('match', 'user')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_match_official(request.user):
            return queryset.filter(user=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False
        if is_league_admin(request.user):
            return True
        return (
            is_match_official(request.user)
            and (obj is None or obj.user_id == request.user.pk)
        )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and is_league_admin(
            request.user
        )

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(
            request,
        ) and is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(
            request,
        ) and is_league_admin(request.user)


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = (
        'match',
        'event_type',
        'player',
        'minute',
        'added_time',
    )

    list_filter = ('event_type',)
    search_fields = (
        'player__first_name',
        'player__last_name',
        'match__home_team__name',
        'match__away_team__name',
    )

    list_select_related = (
        'match',
        'player',
        'related_player',
    )

    ordering = ('match', 'minute')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_match_official(request.user):
            return queryset.filter(match__officials__user=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False
        if obj is None:
            return (
                is_league_admin(request.user)
                or is_match_official(request.user)
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
        return super().has_delete_permission(
            request,
        ) and is_league_admin(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'match' and is_match_official(request.user):
            kwargs['queryset'] = Match.objects.filter(
                officials__user=request.user
            )
        elif (
            db_field.name in ('player', 'related_player')
            and is_match_official(request.user)
        ):
            kwargs['queryset'] = visible_players_for_user(request.user)

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )
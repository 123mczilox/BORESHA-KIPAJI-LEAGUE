from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django import forms
from django.db import models
from django.db import transaction

from apps.accounts.permissions import (
    can_manage_match,
    can_view_match,
    is_league_admin,
    is_match_official,
    is_team_manager,
    visible_players_for_user,
)

from .models import Match, MatchEvent, MatchOfficial, Season, SeasonTeam
from .services import (
    ALLOWED_STATUS_TRANSITIONS,
    assign_match_official,
    create_fixture,
    create_match_event,
    delete_match_event,
    register_team_for_season,
    transition_match,
    update_fixture,
    update_match_event,
)


class MatchAdminForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = (
            'season',
            'home_team',
            'away_team',
            'matchweek',
            'kickoff_time',
            'venue',
            'status',
        )

    def clean(self):
        cleaned_data = super().clean()
        previous_status = self.instance.status
        next_status = cleaned_data.get('status', previous_status)
        if (
            next_status != previous_status
            and next_status not in ALLOWED_STATUS_TRANSITIONS.get(
                previous_status,
                set(),
            )
        ):
            self.add_error('status', 'This match status transition is not allowed.')
        if (
            next_status == Match.Status.SCHEDULED
            and self.instance.started_at is not None
        ):
            self.add_error(
                'status',
                'A match that has started cannot return to scheduled status.',
            )
        if next_status == Match.Status.COMPLETED:
            self.instance.home_score = self.instance.home_score or 0
            self.instance.away_score = self.instance.away_score or 0
        return cleaned_data


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'start_date', 'end_date', 'is_active')
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
            obj,
        ) and is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(
            request,
            obj,
        ) and is_league_admin(request.user)


@admin.register(SeasonTeam)
class SeasonTeamAdmin(admin.ModelAdmin):
    list_display = ('season', 'team', 'created_at')
    list_filter = ('season',)
    search_fields = ('season__name', 'team__name')
    list_select_related = ('season', 'team')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        return (
            super().has_view_permission(request, obj)
            and is_league_admin(request.user)
        )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and is_league_admin(
            request.user
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            raise PermissionDenied('Season-team membership is immutable.')
        membership = register_team_for_season(
            user=request.user,
            team_id=obj.team_id,
            season_id=obj.season_id,
        )
        obj.pk = membership.pk
        obj.created_at = membership.created_at
        obj._state.adding = False
        obj._state.db = membership._state.db


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm
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
    list_filter = ('season', 'status', 'matchweek')
    search_fields = ('home_team__name', 'away_team__name', 'venue')
    date_hierarchy = 'kickoff_time'
    list_select_related = ('season', 'home_team', 'away_team')
    ordering = ('kickoff_time',)
    fields = (
        'season',
        'home_team',
        'away_team',
        'matchweek',
        'kickoff_time',
        'venue',
        'status',
        'home_score',
        'away_score',
    )

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
        if not super().has_view_permission(request, obj):
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
        if not super().has_change_permission(request, obj):
            return False
        if obj is None:
            return is_league_admin(request.user) or is_match_official(
                request.user
            )
        if obj.status in (Match.Status.COMPLETED, Match.Status.CANCELLED):
            return False
        if is_league_admin(request.user):
            return (
                obj.started_at is None
                and obj.status in (
                    Match.Status.SCHEDULED,
                    Match.Status.POSTPONED,
                )
            )
        return can_manage_match(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        if obj is None:
            return (
                'season',
                'home_team',
                'away_team',
                'matchweek',
                'kickoff_time',
                'venue',
            )
        return self.fields

    def get_readonly_fields(self, request, obj=None):
        readonly = ('home_score', 'away_score')
        if obj is not None and not is_league_admin(request.user):
            return readonly + (
                'season',
                'home_team',
                'away_team',
                'matchweek',
                'kickoff_time',
                'venue',
            )
        return readonly

    def save_model(self, request, obj, form, change):
        values = {
            'season': obj.season,
            'home_team': obj.home_team,
            'away_team': obj.away_team,
            'matchweek': obj.matchweek,
            'kickoff_time': obj.kickoff_time,
            'venue': obj.venue,
        }
        if change:
            with transaction.atomic():
                previous = Match.objects.get(pk=obj.pk)
                fixture_changed = any(
                    getattr(previous, field) != getattr(obj, field)
                    for field in (
                        'season',
                        'home_team',
                        'away_team',
                        'matchweek',
                        'kickoff_time',
                        'venue',
                    )
                )
                if fixture_changed:
                    if not is_league_admin(request.user):
                        raise PermissionDenied(
                            'Only League Admins can edit fixture details.'
                        )
                    update_fixture(
                        user=request.user,
                        match_id=obj.pk,
                        values=values,
                    )
                if obj.status != previous.status:
                    transition_match(
                        user=request.user,
                        match_id=obj.pk,
                        status=obj.status,
                    )
                match = Match.objects.get(pk=obj.pk)
        else:
            match = create_fixture(user=request.user, values=values)
        obj.pk = match.pk
        obj._state.adding = False
        obj._state.db = match._state.db


@admin.register(MatchOfficial)
class MatchOfficialAdmin(admin.ModelAdmin):
    list_display = ('match', 'user', 'role')
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
        if not super().has_view_permission(request, obj):
            return False
        return (
            is_league_admin(request.user)
            or (
                is_match_official(request.user)
                and (obj is None or obj.user_id == request.user.pk)
            )
        )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and is_league_admin(
            request.user
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            raise PermissionDenied(
                'Official assignments cannot be edited after creation.'
            )
        assignment = assign_match_official(
            user=request.user,
            match_id=obj.match_id,
            official_user_id=obj.user_id,
            role=obj.role,
        )
        obj.pk = assignment.pk
        obj._state.adding = False
        obj._state.db = assignment._state.db


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = ('match', 'event_type', 'player', 'minute', 'added_time')
    list_filter = ('event_type',)
    search_fields = (
        'player__first_name',
        'player__last_name',
        'match__home_team__name',
        'match__away_team__name',
    )
    list_select_related = ('match', 'player', 'related_player')
    ordering = ('match', 'minute')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_match_official(request.user):
            return queryset.filter(match__officials__user=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if obj is None:
            return is_league_admin(request.user) or is_match_official(
                request.user
            )
        return can_manage_match(request.user, obj.match)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and (
                is_league_admin(request.user)
                or is_match_official(request.user)
            )
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None:
            return is_league_admin(request.user) or is_match_official(
                request.user
            )
        if obj.match.status == Match.Status.COMPLETED:
            return is_league_admin(request.user)
        return (
            obj.match.status == Match.Status.LIVE
            and can_manage_match(request.user, obj.match)
        )

    def has_delete_permission(self, request, obj=None):
        if not is_league_admin(request.user):
            return False
        return (
            obj is None
            or obj.match.status in (
                Match.Status.LIVE,
                Match.Status.COMPLETED,
            )
        )

    def save_model(self, request, obj, form, change):
        values = {
            'event_type': obj.event_type,
            'player': obj.player,
            'related_player': obj.related_player,
            'minute': obj.minute,
            'added_time': obj.added_time,
            'description': obj.description,
        }
        if change:
            event = update_match_event(
                user=request.user,
                event_id=obj.pk,
                values=values,
            )
        else:
            event = create_match_event(
                user=request.user,
                match_id=obj.match_id,
                values=values,
            )
        obj.pk = event.pk
        obj._state.adding = False
        obj._state.db = event._state.db

    def delete_model(self, request, obj):
        delete_match_event(user=request.user, event_id=obj.pk)

    def delete_queryset(self, request, queryset):
        for event_id in queryset.order_by('pk').values_list('pk', flat=True):
            delete_match_event(user=request.user, event_id=event_id)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'match' and is_match_official(request.user):
            from .models import Match

            kwargs['queryset'] = Match.objects.filter(
                officials__user=request.user,
            ).distinct()
        elif db_field.name in ('player', 'related_player'):
            kwargs['queryset'] = visible_players_for_user(request.user)
        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

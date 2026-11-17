from django.contrib import admin
from django.core.exceptions import PermissionDenied

from apps.accounts.permissions import (
    can_view_registration,
    can_view_player,
    is_league_admin,
    is_match_official,
    is_team_manager,
    visible_players_for_user,
)
from .models import Player, PlayerRegistration
from .services import register_player


class PlayerRegistrationInline(admin.TabularInline):
    model = PlayerRegistration
    extra = 0
    show_change_link = True

    fields = (
        'team',
        'season',
        'shirt_number',
        'start_date',
        'end_date',
    )

    def has_view_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):

    list_display = (
        'first_name',
        'last_name',
        'position',
        'date_of_birth',
        'is_active',
    )

    list_filter = (
        'position',
        'is_active',
    )

    search_fields = (
        'first_name',
        'last_name',
    )

    ordering = (
        'first_name',
        'last_name',
    )

    inlines = [PlayerRegistrationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            pk__in=visible_players_for_user(request.user).values('pk')
        )

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_team_manager(request.user)
                or is_match_official(request.user)
            )

        return can_view_player(request.user, obj)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and is_league_admin(request.user)
        )

    def has_change_permission(self, request, obj=None):
        return (
            super().has_change_permission(request)
            and is_league_admin(request.user)
        )

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request)
            and is_league_admin(request.user)
        )


@admin.register(PlayerRegistration)
class PlayerRegistrationAdmin(admin.ModelAdmin):

    list_display = (
        'player',
        'team',
        'season',
        'shirt_number',
        'start_date',
        'end_date',
    )

    list_filter = (
        'season',
        'team',
    )

    search_fields = (
        'player__first_name',
        'player__last_name',
        'team__name',
    )

    list_select_related = (
        'player',
        'team',
        'season',
    )

    ordering = (
        'team',
        'shirt_number',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_league_admin(request.user):
            return queryset

        if is_team_manager(request.user):
            return queryset.filter(
                team__manager_assignments__user=request.user,
                team__manager_assignments__is_active=True,
            ).distinct()

        if is_match_official(request.user):
            from django.db.models import F, Q

            return queryset.filter(
                Q(
                    team__home_matches__officials__user=request.user,
                    team__home_matches__season=F('season'),
                )
                | Q(
                    team__away_matches__officials__user=request.user,
                    team__away_matches__season=F('season'),
                )
            ).distinct()

        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False

        if obj is None:
            return (
                is_league_admin(request.user)
                or is_team_manager(request.user)
                or is_match_official(request.user)
            )

        return can_view_registration(request.user, obj)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and (
                is_league_admin(request.user)
                or is_team_manager(request.user)
            )
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            raise PermissionDenied(
                'Registrations must be changed through player workflows.'
            )

        registration = register_player(
            user=request.user,
            player_id=obj.player_id,
            team_id=obj.team_id,
            season_id=obj.season_id,
            start_date=obj.start_date,
            end_date=obj.end_date,
            shirt_number=obj.shirt_number,
        )
        obj.pk = registration.pk
        obj.created_at = registration.created_at
        obj._state.adding = False
        obj._state.db = registration._state.db

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'team' and is_team_manager(request.user):
            from apps.teams.models import Team

            kwargs['queryset'] = Team.objects.filter(
                manager_assignments__user=request.user,
                manager_assignments__is_active=True,
            ).distinct()
        elif db_field.name == 'player' and is_team_manager(request.user):
            kwargs['queryset'] = visible_players_for_user(request.user)

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )
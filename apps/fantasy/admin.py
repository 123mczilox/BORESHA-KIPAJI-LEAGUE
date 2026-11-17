from django.contrib import admin

from apps.accounts.permissions import (
    can_manage_fantasy_team,
    is_fantasy_manager,
    is_league_admin,
)

from .models import (
    FantasyTeam,
    FantasyPlayerSelection,
    FantasyGameWeek,
    FantasyGameweekMatch,
    PlayerFantasyValue,
    FantasyTransfer,
    FantasyScoringRule,
    PlayerGameweekScore,
    FantasyGameweekScore,
)


class FantasyPlayerSelectionInline(admin.TabularInline):
    model = FantasyPlayerSelection
    extra = 0

    def has_view_permission(self, request, obj=None):
        return obj is not None and can_manage_fantasy_team(
            request.user,
            obj,
        )

    def has_add_permission(self, request, obj=None):
        return obj is not None and can_manage_fantasy_team(
            request.user,
            obj,
        )

    def has_change_permission(self, request, obj=None):
        return obj is not None and can_manage_fantasy_team(
            request.user,
            obj,
        )

    def has_delete_permission(self, request, obj=None):
        return (
            is_league_admin(request.user)
            or is_fantasy_manager(request.user)
            and obj is not None
            and can_manage_fantasy_team(request.user, obj)
        )

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and not is_league_admin(request.user):
            return ('purchase_price', 'selected_at')

        return super().get_readonly_fields(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'player':
            from apps.players.models import Player

            kwargs['queryset'] = Player.objects.filter(is_active=True)

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )


class FantasyGameweekMatchInline(admin.TabularInline):
    model = FantasyGameweekMatch
    extra = 0
    autocomplete_fields = ('match',)


@admin.register(FantasyTeam)
class FantasyTeamAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'manager',
        'season',
        'budget_remaining',
        'total_points',
    )

    list_filter = ('season',)
    search_fields = ('name', 'manager__username')
    list_select_related = ('manager', 'season')

    inlines = [FantasyPlayerSelectionInline]

    readonly_fields = (
        'total_points',
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_fantasy_manager(request.user):
            return queryset.filter(manager=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False
        if obj is None:
            return (
                is_league_admin(request.user)
                or is_fantasy_manager(request.user)
            )
        return can_manage_fantasy_team(request.user, obj)

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and (
                is_league_admin(request.user)
                or is_fantasy_manager(request.user)
            )
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request):
            return False
        if obj is None:
            return (
                is_league_admin(request.user)
                or is_fantasy_manager(request.user)
            )
        return can_manage_fantasy_team(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request)
            and is_league_admin(request.user)
        )

    def get_fields(self, request, obj=None):
        if is_fantasy_manager(request.user) and not is_league_admin(
            request.user
        ):
            return ('season', 'name')

        return super().get_fields(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if (
            obj is not None
            and is_fantasy_manager(request.user)
            and not is_league_admin(request.user)
        ):
            return (*super().get_readonly_fields(request, obj), 'season')

        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if is_fantasy_manager(request.user) and not is_league_admin(
            request.user
        ):
            obj.manager = request.user

        super().save_model(request, obj, form, change)


@admin.register(FantasyGameWeek)
class FantasyGameWeekAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'number',
        'season',
        'deadline',
        'is_current',
        'is_finished',
    )

    list_filter = ('season', 'is_current', 'is_finished')
    search_fields = ('name', 'season__name')
    list_select_related = ('season',)

    inlines = [FantasyGameweekMatchInline]

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(FantasyGameweekMatch)
class FantasyGameweekMatchAdmin(admin.ModelAdmin):
    list_display = ('gameweek', 'match')
    list_filter = ('gameweek__season',)
    search_fields = (
        'match__home_team__name',
        'match__away_team__name',
    )
    autocomplete_fields = ('match',)

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(PlayerFantasyValue)
class PlayerFantasyValueAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'season',
        'initial_price',
        'current_price',
        'updated_at',
    )

    list_filter = ('season',)
    search_fields = (
        'player__first_name',
        'player__last_name',
    )
    list_select_related = ('player', 'season')

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(FantasyTransfer)
class FantasyTransferAdmin(admin.ModelAdmin):
    list_display = (
        'fantasy_team',
        'player_out',
        'player_in',
        'game_week',
        'points_cost',
        'transfer_date',
    )

    list_filter = ('game_week__season', 'game_week')
    search_fields = (
        'fantasy_team__name',
        'player_in__first_name',
        'player_out__first_name',
    )

    readonly_fields = ('transfer_date',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_fantasy_manager(request.user):
            return queryset.filter(fantasy_team__manager=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False
        if obj is None:
            return (
                is_league_admin(request.user)
                or is_fantasy_manager(request.user)
            )
        return can_manage_fantasy_team(request.user, obj.fantasy_team)

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(FantasyScoringRule)
class FantasyScoringRuleAdmin(admin.ModelAdmin):
    list_display = (
        'season',
        'event_type',
        'position',
        'points',
        'is_active',
    )

    list_filter = ('season', 'event_type', 'position', 'is_active')
    list_editable = ('points', 'is_active')
    search_fields = ('description',)

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(PlayerGameweekScore)
class PlayerGameweekScoreAdmin(admin.ModelAdmin):
    list_display = (
        'player',
        'gameweek',
        'minutes_played',
        'points',
        'is_final',
    )

    list_filter = ('gameweek__season', 'is_final')
    search_fields = (
        'player__first_name',
        'player__last_name',
    )

    readonly_fields = (
        'player',
        'gameweek',
        'minutes_played',
        'points',
        'scoring_breakdown',
        'updated_at',
    )

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(FantasyGameweekScore)
class FantasyGameweekScoreAdmin(admin.ModelAdmin):
    list_display = (
        'fantasy_team',
        'gameweek',
        'points_earned',
        'transfer_points_cost',
        'total_points',
        'rank',
    )

    list_filter = ('gameweek__season', 'gameweek')
    search_fields = ('fantasy_team__name',)

    readonly_fields = (
        'fantasy_team',
        'gameweek',
        'points_earned',
        'transfer_points_cost',
        'total_points',
        'rank',
        'updated_at',
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_league_admin(request.user):
            return queryset
        if is_fantasy_manager(request.user):
            return queryset.filter(fantasy_team__manager=request.user)
        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False
        if obj is None:
            return (
                is_league_admin(request.user)
                or is_fantasy_manager(request.user)
            )
        return can_manage_fantasy_team(request.user, obj.fantasy_team)

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)
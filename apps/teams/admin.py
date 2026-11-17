from django.contrib import admin

from apps.accounts.permissions import (
    can_manage_team,
    is_league_admin,
    is_team_manager,
)

from .models import Team, TeamManagerAssignment

# Register your models here.


class TeamManagerAssignmentInline(admin.TabularInline):
    model = TeamManagerAssignment
    extra = 1
    autocomplete_fields = ['user']

    def has_view_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_add_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'short_name',
        'county',
        'is_active',
        'created_at',
    )

    list_filter = ('is_active', 'county')
    search_fields = ('name', 'short_name', 'county')
    ordering = ('name',)

    inlines = [TeamManagerAssignmentInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_league_admin(request.user):
            return queryset

        if is_team_manager(request.user):
            return queryset.filter(
                manager_assignments__user=request.user,
                manager_assignments__is_active=True,
            ).distinct()

        return queryset.none()

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request):
            return False

        return (
            obj is None and (
                is_league_admin(request.user)
                or is_team_manager(request.user)
            )
            or obj is not None and can_manage_team(request.user, obj)
        )

    def has_add_permission(self, request):
        return (
            super().has_add_permission(request)
            and is_league_admin(request.user)
        )

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request):
            return False

        return (
            obj is None and (
                is_league_admin(request.user)
                or is_team_manager(request.user)
            )
            or obj is not None and can_manage_team(request.user, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return (
            super().has_delete_permission(request)
            and is_league_admin(request.user)
        )

    def get_fields(self, request, obj=None):
        if is_team_manager(request.user) and not is_league_admin(request.user):
            return ('short_name', 'description')

        return super().get_fields(request, obj)


@admin.register(TeamManagerAssignment)
class TeamManagerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'team',
        'is_active',
        'assigned_at',
    )

    list_filter = ('is_active', 'team')
    search_fields = (
        'user__username',
        'user__email',
        'team__name',
    )
    autocomplete_fields = ['user', 'team']
    readonly_fields = ('assigned_at',)

    def has_view_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_add_permission(self, request):
        return is_league_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_league_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_league_admin(request.user)
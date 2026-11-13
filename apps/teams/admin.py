from django.contrib import admin
from .models import Team, TeamManagerAssignment

# Register your models here.


class TeamManagerAssignmentInline(admin.TabularInline):
    model = TeamManagerAssignment
    extra = 1
    autocomplete_fields = ['user']


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
from django.contrib import admin
from .models import Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'opportunity_type',
        'provider',
        'status',
        'is_featured',
        'application_deadline',
        'published_at',
    )

    list_filter = (
        'opportunity_type',
        'status',
        'is_featured',
    )

    search_fields = (
        'title',
        'provider',
        'description',
        'location',
    )

    prepopulated_fields = {
        'slug': ('title',),
    }

    list_editable = (
        'status',
        'is_featured',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'published_at',
    )

    date_hierarchy = 'application_deadline'

    ordering = (
        'application_deadline',
        '-created_at',
    )
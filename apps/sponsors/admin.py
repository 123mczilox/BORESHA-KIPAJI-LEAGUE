from django.contrib import admin
from .models import Sponsor


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'level',
        'is_active',
        'display_order',
        'partnership_start_date',
        'partnership_end_date',
    )

    list_filter = (
        'level',
        'is_active',
    )

    search_fields = (
        'name',
        'description',
    )

    list_editable = (
        'level',
        'is_active',
        'display_order',
    )

    ordering = (
        'display_order',
        'name',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )
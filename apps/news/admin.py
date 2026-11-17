from django.contrib import admin
from .models import NewsCategory, NewsArticle


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'author',
        'status',
        'is_featured',
        'published_at',
    )

    list_filter = (
        'status',
        'category',
        'is_featured',
    )

    search_fields = (
        'title',
        'content',
        'author__username',
    )

    prepopulated_fields = {'slug': ('title',)}

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    date_hierarchy = 'published_at'
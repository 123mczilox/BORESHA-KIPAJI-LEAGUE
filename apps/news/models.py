from django.conf import settings
from django.db import models
from django.utils import timezone


class NewsCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'news categories'

    def __str__(self):
        return self.name


class NewsArticle(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.ForeignKey(
        NewsCategory,
        on_delete=models.PROTECT,
        related_name='articles'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news_articles'
    )
    featured_image = models.ImageField(
        upload_to='news/',
        blank=True
    )
    content = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT
    )
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(
                fields=['status', '-published_at'],
                name='news_status_pub_idx'
            ),
        ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        should_set_publication_time = (
            update_fields is None or 'status' in update_fields
        )

        if (
            self.status == self.Status.PUBLISHED
            and self.published_at is None
            and should_set_publication_time
        ):
            self.published_at = timezone.now()
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'published_at'}

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

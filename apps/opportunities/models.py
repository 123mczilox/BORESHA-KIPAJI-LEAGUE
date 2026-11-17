from django.conf import settings
from django.db import models
from django.utils import timezone


class Opportunity(models.Model):

    class OpportunityType(models.TextChoices):
        SCHOLARSHIP = 'scholarship', 'Scholarship'
        TRIAL = 'trial', 'Trial'
        ACADEMY = 'academy', 'Academy'
        TRAINING = 'training', 'Training'
        COMPETITION = 'competition', 'Competition'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    opportunity_type = models.CharField(
        max_length=20,
        choices=OpportunityType.choices
    )
    description = models.TextField()
    provider = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    eligibility_requirements = models.TextField(blank=True)
    application_instructions = models.TextField(blank=True)
    application_url = models.URLField(blank=True)
    application_deadline = models.DateField(
        null=True,
        blank=True,
        db_index=True
    )
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_opportunities'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['application_deadline', '-created_at']
        indexes = [
            models.Index(
                fields=['status', 'opportunity_type', 'application_deadline'],
                name='opp_status_type_deadline_idx'
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

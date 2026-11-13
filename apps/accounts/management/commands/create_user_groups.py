from django.core.management.base import BaseCommand

from apps.accounts.permissions import create_user_groups


class Command(BaseCommand):

    help = 'Create default Boresha Kipaji League user groups'

    def handle(self, *args, **options):

        create_user_groups()

        self.stdout.write(
            self.style.SUCCESS(
                'Successfully created user groups and assigned permissions.'
            )
        )
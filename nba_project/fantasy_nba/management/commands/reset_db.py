# fantasy_nba/management/commands/reset_db.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection

class Command(BaseCommand):
    help = 'Resets all data in the database (keeps schema)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm database reset',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.ERROR(
                'Add --confirm flag to reset the database'
            ))
            return

        self.stdout.write('Starting database reset...')
        
        try:
            # Flush the database
            call_command('flush', '--no-input', verbosity=0)
            self.stdout.write(self.style.SUCCESS('Database reset completed!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error resetting database: {e}'))

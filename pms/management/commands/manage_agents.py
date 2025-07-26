from django.core.management.base import BaseCommand
from pms.models import Agent


class Command(BaseCommand):
    help = 'Manage booking agents/sources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all agents',
        )
        parser.add_argument(
            '--add',
            type=str,
            help='Add a new agent with the given name',
        )
        parser.add_argument(
            '--deactivate',
            type=str,
            help='Deactivate an agent by name',
        )
        parser.add_argument(
            '--activate',
            type=str,
            help='Activate an agent by name',
        )
        parser.add_argument(
            '--order',
            type=int,
            help='Display order for the agent (use with --add)',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_agents()
        elif options['add']:
            self.add_agent(options['add'], options.get('order', 0))
        elif options['deactivate']:
            self.deactivate_agent(options['deactivate'])
        elif options['activate']:
            self.activate_agent(options['activate'])
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --list, --add, --activate, or --deactivate')
            )

    def list_agents(self):
        agents = Agent.objects.all().order_by('display_order', 'name')
        if not agents:
            self.stdout.write(self.style.WARNING('No agents found.'))
            return

        self.stdout.write(self.style.SUCCESS('Current agents:'))
        self.stdout.write('-' * 60)
        for agent in agents:
            status = "Active" if agent.is_active else "Inactive"
            self.stdout.write(
                f"{agent.display_order:3d}. {agent.name:<30} [{status}]"
            )

    def add_agent(self, name, order):
        try:
            agent, created = Agent.objects.get_or_create(
                name=name,
                defaults={'display_order': order, 'is_active': True}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully added agent: {name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Agent already exists: {name}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error adding agent: {e}')
            )

    def deactivate_agent(self, name):
        try:
            agent = Agent.objects.get(name=name)
            agent.is_active = False
            agent.save()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deactivated agent: {name}')
            )
        except Agent.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Agent not found: {name}')
            )

    def activate_agent(self, name):
        try:
            agent = Agent.objects.get(name=name)
            agent.is_active = True
            agent.save()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully activated agent: {name}')
            )
        except Agent.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Agent not found: {name}')
            )
from django.core.management.base import BaseCommand
from territories.models import Commune
from elections.models import BureauDeVote, Election

class Command(BaseCommand):
    help = 'Generates exactly one "محضر بلدية" (Commune PV) for all 1541 communes'

    def handle(self, *args, **kwargs):
        # 1. Find Active Election
        active_election = Election.objects.filter(status='open').order_by('-election_date').first()
        if not active_election:
            self.stdout.write(self.style.ERROR('❌ No active election found. Please create an election with status "open" first.'))
            return
            
        self.stdout.write(self.style.SUCCESS(f'\n🗳️ Target Election: {active_election.name_fr} (ID: {active_election.id})'))
        
        # 2. Get all communes
        total_communes = Commune.objects.count()
        self.stdout.write(f'🇩🇿 Total Communes in Database: {total_communes}')
        
        # 3. Generate PVs safely
        created_count = 0
        existing_count = 0
        
        communes = Commune.objects.all()
        
        for commune in communes:
            pv_code = f"PV_{commune.code}"
            pv_name = f"محضر بلدية {commune.name_ar}"
            
            # get_or_create ensures we don't duplicate, and keeps existing data safe
            obj, created = BureauDeVote.objects.get_or_create(
                commune=commune,
                election=active_election,
                code=pv_code,
                defaults={
                    'name': pv_name,
                    'registered_voters': 0,
                    'is_deleted': False
                }
            )
            
            if created:
                created_count += 1
            else:
                existing_count += 1
                
        self.stdout.write(self.style.SUCCESS(f'\n✅ SUCCESS!'))
        self.stdout.write(f'📝 Already existed (kept safe): {existing_count}')
        self.stdout.write(f'🆕 Newly created: {created_count}')
        self.stdout.write(self.style.SUCCESS(f'🎯 Total PVs now available: {existing_count + created_count}\n'))
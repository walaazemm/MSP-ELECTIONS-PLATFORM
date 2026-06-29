import json
from django.core.management.base import BaseCommand
from territories.models import Wilaya, Commune
from elections.models import ListResult, StationResult, BureauDeVote

class Command(BaseCommand):
    help = 'WIPES ALL DATA (Bureaux, Results, Communes) and imports fresh from JSON'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.ERROR('\n☢️ WARNING: This will delete ALL Bureaux, Results, and Communes!\n'))
        
        # 1. Delete dependents first to bypass RestrictedError
        self.stdout.write('🗑️ Deleting List Results...')
        ListResult.objects.all().delete()
        
        self.stdout.write('🗑️ Deleting Station Results...')
        StationResult.objects.all().delete()
        
        self.stdout.write('🗑️ Deleting Bureaux (Centers)...')
        BureauDeVote.objects.all().delete()
        
        self.stdout.write('🗑️ Deleting Communes...')
        deleted_count = Commune.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted_count} records.\n'))

        # 2. Import Fresh Data
        self.stdout.write(self.style.WARNING('📂 Loading algeria_cities.json...\n'))
        try:
            with open(r'D:\WALAA\MSP\APPS and Systems\msp elections\msp-elections\elections\management\commands\algeria_cities.json', 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ algeria_cities.json not found!'))
            return

        wilaya_cache = {}
        created_count = 0

        for item in raw_data:
            clean = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in item.items()}
            
            w_code = clean.get('wilaya_code')
            c_code = clean.get('code_commune')
            
            if w_code not in wilaya_cache:
                wilaya, _ = Wilaya.objects.get_or_create(
                    code=w_code,
                    defaults={'name_ar': clean.get('wilaya_name'), 'name_fr': clean.get('wilaya_name_fr')}
                )
                wilaya_cache[w_code] = wilaya
                
            Commune.objects.create(
                wilaya=wilaya_cache[w_code],
                code=c_code,
                name_ar=clean.get('commune_name'),
                name_fr=clean.get('commune_name_fr')
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n🎉 SUCCESS! Imported {created_count} fresh communes.'))
        self.stdout.write(self.style.SUCCESS(f'🇩🇿 Total Communes in DB: {Commune.objects.count()}\n'))
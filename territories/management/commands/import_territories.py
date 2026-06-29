import csv
from io import StringIO
from django.core.management.base import BaseCommand
from territories.models import Wilaya, Commune
from elections.models import BureauDeVote, StationResult, ListResult

class Command(BaseCommand):
    help = 'Clears and imports all 69 Wilayas and Communes (Fixes Int/Str mismatch).'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('⚠️  WARNING: This will delete all existing Bureaux, Results, Communes, and Wilayas.'))
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            return

        self.stdout.write('Clearing data...')
        ListResult.objects.all().delete()
        StationResult.objects.all().delete()
        BureauDeVote.objects.all().delete()
        Commune.objects.all().delete()
        Wilaya.objects.all().delete()

        file_path = 'algeria_wilayas_communes_2026.csv' 
        
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                raw_content = f.read()
            
            # Bulletproof line splitting
            raw_content = raw_content.replace('\r\n', '\n').replace('\r', '\n')
            lines = raw_content.split('\n')
            
            if lines and 'wilaya_code' in lines[0].lower():
                lines = lines[1:]

            wilaya_instances = []
            wilaya_codes_seen = set()
            
            # Pass 1: Wilayas
            for line in lines:
                if not line.strip(): continue
                row = next(csv.reader(StringIO(line)))
                if len(row) < 5: continue
                
                w_code = str(row[0]).strip().zfill(2)
                w_name_fr = str(row[1]).strip()
                w_name_ar = str(row[2]).strip() if len(row) > 2 and row[2].strip() else w_name_fr
                
                if not w_code or not w_name_fr or w_code in wilaya_codes_seen: 
                    continue
                    
                wilaya_codes_seen.add(w_code)
                wilaya_instances.append(Wilaya(code=w_code, name_fr=w_name_fr, name_ar=w_name_ar))

            self.stdout.write(f'Creating {len(wilaya_instances)} Wilayas...')
            Wilaya.objects.bulk_create(wilaya_instances)
            
            #  CRITICAL FIX: Force keys to be zero-padded strings to avoid Int/Str mismatch
            db_wilayas = {str(w.code).zfill(2): w for w in Wilaya.objects.all()}
            self.stdout.write(self.style.SUCCESS(f'Loaded {len(db_wilayas)} Wilayas into memory. Sample keys: {list(db_wilayas.keys())[:5]}'))

            # Pass 2: Communes
            commune_instances = []
            skipped_count = 0
            
            for line in lines:
                if not line.strip(): continue
                row = next(csv.reader(StringIO(line)))
                if len(row) < 5: 
                    skipped_count += 1
                    continue
                
                w_code = str(row[0]).strip().zfill(2)
                c_code = str(row[3]).strip()
                c_name_fr = str(row[4]).strip()
                c_name_ar = str(row[5]).strip() if len(row) > 5 and row[5].strip() else c_name_fr
                
                if not c_code or not c_name_fr:
                    skipped_count += 1
                    continue
                    
                if w_code not in db_wilayas:
                    if skipped_count < 3:
                        self.stdout.write(self.style.ERROR(f"Debug - Wilaya {w_code} NOT FOUND in db_wilayas! Row: {row}"))
                    skipped_count += 1
                    continue
                    
                commune_instances.append(
                    Commune(
                        wilaya=db_wilayas[w_code],
                        code=c_code,
                        name_fr=c_name_fr,
                        name_ar=c_name_ar
                    )
                )
                
            self.stdout.write(f'Creating {len(commune_instances)} Communes...')
            Commune.objects.bulk_create(commune_instances, batch_size=500)
                
            self.stdout.write(self.style.SUCCESS(f'\n SUCCESS! Imported {len(wilaya_instances)} Wilayas and {len(commune_instances)} Communes.'))
            if skipped_count > 0:
                self.stdout.write(self.style.WARNING(f'(Note: Skipped {skipped_count} malformed/empty lines)'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f' Error: {str(e)}'))
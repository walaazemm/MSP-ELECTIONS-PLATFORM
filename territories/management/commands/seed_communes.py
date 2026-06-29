from django.core.management.base import BaseCommand
from territories.models import Wilaya, Commune, CommuneSettings

class Command(BaseCommand):
    help = 'Seeds a realistic subset of communes for testing'

    def handle(self, *args, **kwargs):
        # Sample communes mapped to their Wilaya codes
        sample_data = {
            16: [("16001", "Alger Centre", "الجزائر الوسطى"), ("16002", "Sidi M'Hamed", "سيدي امحمد"), ("16003", "El Madania", "المدنية"), ("16004", "Hussein Dey", "حسين داي"), ("16005", "Kouba", "القبة"), ("16006", "El Harrach", "الحراش"), ("16007", "Bab Ezzouar", "باب الزوار"), ("16008", "Dar El Beïda", "الدار البيضاء"), ("16009", "Bab El Oued", "باب الوادي"), ("16010", "Bouzareah", "بوزريعة")],
            31: [("31001", "Oran", "وهران"), ("31002", "Bir El Djir", "بئر الجير"), ("31003", "Es Senia", "السانية"), ("31004", "Aïn El Turk", "عين الترك"), ("31005", "Arzew", "أرزيو")],
            25: [("25001", "Constantine", "قسنطينة"), ("25002", "El Khroub", "الخروب"), ("25003", "Aïn Smara", "عين سمارة"), ("25004", "Hamma Bouziane", "حامة بوزيان")],
            9: [("9001", "Blida", "البليدة"), ("9002", "Boufarik", "بوفاريك"), ("9003", "Bougara", "بوقرة")],
            15: [("15001", "Tizi Ouzou", "تيزي وزو"), ("15002", "Draa El Mizan", "ذراع الميزان"), ("15003", "Azazga", "عزازقة")],
            6: [("6001", "Béjaïa", "بجاية"), ("6002", "Akbou", "أقبو"), ("6003", "Sidi Aïch", "سيدي عيش")],
            5: [("5001", "Batna", "باتنة"), ("5002", "Barika", "بريكة"), ("5003", "Aïn Touta", "عين التوتة")],
            19: [("19001", "Sétif", "سطيف"), ("19002", "El Eulma", "العلمة"), ("19003", "Aïn Oulmene", "عين ولمان")],
            # Seed at least one for every other wilaya
            2: [("2001", "Chlef", "الشلف")], 3: [("3001", "Laghouat", "الأغواط")], 4: [("4001", "Oum El Bouaghi", "أم البواقي")],
            7: [("7001", "Biskra", "بسكرة")], 8: [("8001", "Béchar", "بشار")], 10: [("10001", "Bouira", "البويرة")],
            11: [("11001", "Tamanrasset", "تمنراست")], 12: [("12001", "Tébessa", "تبسة")], 13: [("13001", "Tlemcen", "تلمسان")],
            14: [("14001", "Tiaret", "تيارت")], 17: [("17001", "Djelfa", "الجلفة")], 18: [("18001", "Jijel", "جيجل")],
            20: [("20001", "Saïda", "سعيدة")], 21: [("21001", "Skikda", "سكيكدة")], 22: [("22001", "Sidi Bel Abbès", "سيدي بلعباس")],
            23: [("23001", "Annaba", "عنابة")], 24: [("24001", "Guelma", "قالمة")], 26: [("26001", "Médéa", "المدية")],
            27: [("27001", "Mostaganem", "مستغانم")], 28: [("28001", "M'Sila", "المسيلة")], 29: [("29001", "Mascara", "معسكر")],
            30: [("30001", "Ouargla", "ورقلة")], 32: [("32001", "El Bayadh", "البيض")], 33: [("33001", "Illizi", "إليزي")],
            34: [("34001", "Bordj Bou Arreridj", "برج بوعريريج")], 35: [("35001", "Boumerdès", "بومرداس")], 36: [("36001", "El Tarf", "الطارف")],
            37: [("37001", "Tindouf", "تندوف")], 38: [("38001", "Tissemsilt", "تيسمسيلت")], 39: [("39001", "El Oued", "الوادي")],
            40: [("40001", "Khenchela", "خنشلة")], 41: [("41001", "Souk Ahras", "سوق أهراس")], 42: [("42001", "Tipaza", "تيبازة")],
            43: [("43001", "Mila", "ميلة")], 44: [("44001", "Aïn Defla", "عين الدفلى")], 45: [("45001", "Naâma", "النعامة")],
            46: [("46001", "Aïn Témouchent", "عين تموشنت")], 47: [("47001", "Ghardaïa", "غرداية")], 48: [("48001", "Relizane", "غليزان")],
            49: [("49001", "El M'Ghair", "المغير")], 50: [("50001", "El Meniaa", "المنيعة")], 51: [("51001", "Ouled Djellal", "أولاد جلال")],
            52: [("52001", "Bordj Badji Mokhtar", "برج باجي مختار")], 53: [("53001", "Béni Abbès", "بني عباس")], 54: [("54001", "Timimoun", "تيميمون")],
            55: [("55001", "Touggourt", "تقرت")], 56: [("56001", "Djanet", "جانت")], 57: [("57001", "In Salah", "عين صالح")], 58: [("58001", "In Guezzam", "عين قزام")],
        }
        
        created_count = 0
        for wilaya_code, communes in sample_data.items():
            try:
                wilaya = Wilaya.objects.get(code=wilaya_code)
                for code, name_fr, name_ar in communes:
                    commune, created = Commune.objects.get_or_create(
                        wilaya=wilaya, code=code,
                        defaults={'name_fr': name_fr, 'name_ar': name_ar}
                    )
                    if created:
                        # Spec: Default is false, but we set to true for testing
                        CommuneSettings.objects.create(commune=commune, allow_bureau_creation=True) 
                        created_count += 1
            except Wilaya.DoesNotExist:
                pass
                
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} communes!'))
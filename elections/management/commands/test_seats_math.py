from django.core.management.base import BaseCommand
from elections.views import calculate_seats_allocation
import math

class Command(BaseCommand):
    help = 'Tests the Algerian Electoral Law Seat Allocation Engine'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n🇩🇿 Testing Algerian Electoral Law Engine (5% Threshold + Largest Remainder)\n'))
        
        # SCENARIO: Your real data
        valid_votes_raw = 17283
        total_seats = 11
        
        list_votes = {
            1: 6427,  # List 1 (MSP)
            2: 7328,  # List 2 (FLN)
            3: 2008,  # List 3 (RND)
            4: 217,   # List 4 (Eliminated, < 5%)
            5: 1053,
            6: 250,
        }
        
        # Run the engine
        calculation_result = calculate_seats_allocation(valid_votes_raw, list_votes, total_seats)
        
        #  FIX: Extract the 'lists' and 'meta' dictionaries properly
        results = calculation_result['lists']
        meta = calculation_result['meta']
        
        self.stdout.write(f"Raw Valid Votes: {valid_votes_raw}")
        self.stdout.write(f"Total Seats: {total_seats}")
        self.stdout.write(f"Threshold (5%): {meta['threshold']}")
        self.stdout.write(f"Eliminated Votes: {meta['eliminated_votes']}")
        self.stdout.write(f"New Valid Votes: {meta['new_valid_votes']}")
        self.stdout.write(f"Quotient (سعر المقعد): {meta['quotient']}")
        self.stdout.write("-" * 50)

        # Expected results based on the math:
        # Quotient = ceil(9347 / 8) = 1169
        # List 1: 3588 / 1169 = 3 seats (Remainder: 81)
        # List 2: 2894 / 1169 = 2 seats (Remainder: 556) -> Gets +1 from Largest Remainder
        # List 3: 2433 / 1169 = 2 seats (Remainder: 95)
        expected = {
            1: 4, 
            2: 5, 
            3: 1, 
            4: 0, 
            5: 1, 
            6: 0
        }
        
        all_passed = True
        
        #  FIX: Iterate only over the 'lists' dictionary
        for lid, data in results.items():
            seats = data['seats']
            status = data['status']
            exp_seats = expected[lid]
            
            if seats == exp_seats:
                self.stdout.write(self.style.SUCCESS(f" List {lid}: {seats} seats (Status: {status}) | EXPECTED: {exp_seats}"))
            else:
                self.stdout.write(self.style.ERROR(f" List {lid}: {seats} seats (Status: {status}) | EXPECTED: {exp_seats}"))
                all_passed = False
                
        self.stdout.write("-" * 50)
        if all_passed:
            self.stdout.write(self.style.SUCCESS("\n🎉 ALL TESTS PASSED! The math engine is 100% legally accurate.\n"))
        else:
            self.stdout.write(self.style.ERROR("\n⚠️ SOME TESTS FAILED! Check the math engine.\n"))
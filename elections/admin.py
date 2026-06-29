from django.contrib import admin
from .models import Election, BureauDeVote, StationResult, ListResult, ElectionList, ResultAuditLog

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('name_fr', 'election_date', 'status', 'total_seats')
    list_filter = ('status', 'election_date')

@admin.register(BureauDeVote)
class BureauDeVoteAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'commune', 'election', 'registered_voters', 'is_deleted')
    list_filter = ('election', 'commune__wilaya', 'is_deleted')
    search_fields = ('code', 'name', 'commune__name_ar')
    # Prevents loading all communes into a massive cursor
    raw_id_fields = ('commune',) 

@admin.register(StationResult)
class StationResultAdmin(admin.ModelAdmin):
    list_display = ('bureau', 'election', 'submitted_at', 'total_votes_cast', 'is_deleted')
    list_filter = ('election', 'is_deleted')
    # Prevents the cursor crash by using a search popup instead of a dropdown
    raw_id_fields = ('bureau', 'submitted_by', 'last_edited_by') 

@admin.register(ListResult)
class ListResultAdmin(admin.ModelAdmin):
    #  FIX: Removed 'is_deleted' because ListResult doesn't have it
    list_display = ('station_result', 'election_list', 'votes')
    raw_id_fields = ('station_result', 'election_list')

@admin.register(ElectionList)
class ElectionListAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'election', 'wilaya', 'is_our_party', 'is_active')
    list_filter = ('election', 'is_our_party', 'is_active', 'wilaya')
    search_fields = ('name_ar', 'name_fr')
    raw_id_fields = ('wilaya',)

@admin.register(ResultAuditLog)
class ResultAuditLogAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'record_id', 'action', 'changed_by', 'timestamp')
    list_filter = ('action', 'table_name', 'timestamp')
    search_fields = ('record_id', 'notes', 'changed_by__username')
    readonly_fields = ('table_name', 'record_id', 'action', 'changed_by', 'timestamp', 'old_values', 'new_values', 'notes')
    
    # Prevent anyone from manually editing or adding logs via the Admin panel
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False
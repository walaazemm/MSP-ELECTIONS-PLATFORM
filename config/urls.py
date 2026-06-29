from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, Case, When, Value, IntegerField, Subquery, OuterRef
from django.db.models.functions import TruncDate
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.core.cache import cache  # 🚀 PILLAR 2: REDIS CACHE IMPORT
from datetime import datetime, timedelta
from elections.models import Election, BureauDeVote, StationResult, ListResult, ElectionList
from territories.models import Wilaya, Commune
from elections.views import export_results, calculate_seats_allocation

@login_required
def wilaya_detail(request, wilaya_code):
    """Show detailed results for a specific wilaya"""
    try:
        role_obj = request.user.role_profile
        role = role_obj.role
    except ObjectDoesNotExist:
        return redirect('no_role')

    try:
        wilaya = Wilaya.objects.get(code=wilaya_code)
    except Wilaya.DoesNotExist:
        messages.error(request, "الولاية غير موجودة")
        return redirect('home')

    if role == 'commune' and wilaya.id != role_obj.commune.wilaya.id:
        messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الولاية")
        return redirect('home')
    elif role == 'wilaya' and wilaya.id != role_obj.wilaya.id:
        messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الولاية")
        return redirect('home')

    active_election = Election.objects.filter(status='open').order_by('-election_date').first()
    
    bureaux_qs = BureauDeVote.objects.filter(
        commune__wilaya=wilaya, is_deleted=False
    ).select_related('commune__wilaya', 'election')
    
    if active_election:
        bureaux_qs = bureaux_qs.filter(election=active_election)

    total_bureaux = bureaux_qs.count()
    reported_bureaux = bureaux_qs.filter(result__isnull=False, result__is_deleted=False).distinct().count()
    
    valid_sr = StationResult.objects.filter(bureau__in=bureaux_qs, is_deleted=False, election=active_election)
    station_aggr = valid_sr.aggregate(
        total_registered=Sum('registered_voters', default=0),
        total_present=Sum('total_votes_cast', default=0),
        total_null=Sum('null_votes', default=0)
    )
    
    valid_sr_ids = valid_sr.values_list('id', flat=True)
    msp_votes_sum = ListResult.objects.filter(
        station_result_id__in=valid_sr_ids,
        election_list__is_our_party=True
    ).aggregate(total=Sum('votes', default=0))['total'] or 0

    valid_votes_total = (station_aggr['total_present'] or 0) - (station_aggr['total_null'] or 0)

    stats = {
        'registered_voters': station_aggr['total_registered'] or 0,
        'total_votes_cast': station_aggr['total_present'] or 0,
        'valid_votes': valid_votes_total,
        'msp_votes': msp_votes_sum,
        'total_bureaux': total_bureaux,
        'reported_bureaux': reported_bureaux,
        'turnout_percent': round((station_aggr['total_present'] or 0) / max(station_aggr['total_registered'] or 0, 1) * 100, 1),
        'msp_percent': round(msp_votes_sum / max(valid_votes_total, 1) * 100, 1),
        'completion_percent': round(reported_bureaux / max(total_bureaux, 1) * 100, 1),
    }

    if active_election:
        for c in Commune.objects.filter(wilaya=wilaya):
            BureauDeVote.objects.get_or_create(
                commune=c, election=active_election, code=f"PV_{c.code}",
                defaults={'name': f'محضر بلدية {c.name_ar}', 'registered_voters': 0, 'is_deleted': False}
            )

    pv_id_subquery = BureauDeVote.objects.filter(
        commune_id=OuterRef('id'), election=active_election, code__startswith="PV_", is_deleted=False
    ).values('id')[:1]

    commune_msp_subquery = ListResult.objects.filter(
        station_result__bureau__commune_id=OuterRef('id'), station_result__bureau__election=active_election,
        station_result__bureau__is_deleted=False, station_result__is_deleted=False, election_list__is_our_party=True
    ).values('station_result__bureau__commune_id').annotate(total_msp=Sum('votes')).values('total_msp')

    communes_qs = Commune.objects.filter(wilaya=wilaya).select_related('wilaya').annotate(
        total_bureaux=Count('bureaux', filter=Q(bureaux__election=active_election, bureaux__is_deleted=False), distinct=True),
        reported_bureaux=Count('bureaux', filter=Q(bureaux__election=active_election, bureaux__result__isnull=False, bureaux__result__is_deleted=False, bureaux__is_deleted=False), distinct=True),
        msp_votes=Subquery(commune_msp_subquery, output_field=IntegerField()),
        pv_id=Subquery(pv_id_subquery, output_field=IntegerField())
    ).order_by('code')

    recent_activities = StationResult.objects.filter(
        bureau__commune__wilaya=wilaya, bureau__is_deleted=False, is_deleted=False
    ).select_related('bureau__commune', 'submitted_by').order_by('-submitted_at')[:10]

    # 🚀 PILLAR 2: CACHED SEAT PROJECTION LOGIC
    total_seats = wilaya.total_seats if hasattr(wilaya, 'total_seats') and wilaya.total_seats else 4
    seats_projection = {}
    seats_meta = {}
    
    if active_election and valid_votes_total > 0:
        cache_key = f"wilaya_detail_math_{wilaya.id}_{active_election.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            # 🏎️ INSTANT LOAD FROM RAM
            seats_projection = cached_data['seats_projection']
            seats_meta = cached_data['seats_meta']
            total_seats = cached_data['total_seats']
        else:
            # 🐢 HEAVY LIFTING (CALCULATED ONLY ONCE EVERY 2 MINUTES)
            all_list_votes = ListResult.objects.filter(station_result_id__in=valid_sr_ids).values(
                'election_list_id', 'election_list__name_ar', 'election_list__is_our_party'
            ).annotate(total_votes=Sum('votes'))
            
            list_votes_dict = {item['election_list_id']: item['total_votes'] for item in all_list_votes}
            calc_result = calculate_seats_allocation(valid_votes_total, list_votes_dict, total_seats)
            
            seats_projection = calc_result.get('lists', {})
            seats_meta = calc_result.get('meta', {})
            
            for item in all_list_votes:
                lid = item['election_list_id']
                if lid in seats_projection:
                    seats_projection[lid]['name'] = item['election_list__name_ar']
                    seats_projection[lid]['is_our_party'] = item['election_list__is_our_party']
                    
            # 💾 SAVE TO CACHE FOR 120 SECONDS
            cache.set(cache_key, {
                'seats_projection': seats_projection,
                'seats_meta': seats_meta,
                'total_seats': total_seats
            }, timeout=120)

    context = {
        'wilaya': wilaya, 'stats': stats, 'communes': communes_qs, 'recent_activities': recent_activities,
        'active_election': active_election, 'active_page': 'wilaya_detail', 'role': role,
        'seats_projection': seats_projection, 'seats_meta': seats_meta, 'total_seats': total_seats,
    }
    return render(request, 'dashboard_wilaya_detail.html', context)


@login_required
def dashboard_router(request):
    try:
        role = request.user.role_profile.role
        role_obj = request.user.role_profile
    except ObjectDoesNotExist:
        return redirect('no_role')

    active_election = Election.objects.filter(status='open').order_by('-election_date').first()
    bureaux_qs = BureauDeVote.objects.select_related('commune__wilaya').filter(is_deleted=False)
    
    if role == 'commune': bureaux_qs = bureaux_qs.filter(commune=role_obj.commune)
    elif role == 'wilaya': bureaux_qs = bureaux_qs.filter(commune__wilaya=role_obj.wilaya)
    if active_election: bureaux_qs = bureaux_qs.filter(election=active_election)

    total_bureaux = bureaux_qs.count()
    reported_bureaux = bureaux_qs.filter(result__isnull=False, result__is_deleted=False).distinct().count()
    
    valid_sr = StationResult.objects.filter(bureau__in=bureaux_qs, is_deleted=False, election=active_election)
    station_aggr = valid_sr.aggregate(
        total_registered=Sum('registered_voters', default=0),
        total_present=Sum('total_votes_cast', default=0),
        total_null=Sum('null_votes', default=0)
    )
    valid_sr_ids = valid_sr.values_list('id', flat=True)
    msp_votes_sum = ListResult.objects.filter(
        station_result_id__in=valid_sr_ids, election_list__is_our_party=True
    ).aggregate(total=Sum('votes', default=0))['total'] or 0

    valid_votes_total = (station_aggr['total_present'] or 0) - (station_aggr['total_null'] or 0)
    stats = {
        'registered_voters': station_aggr['total_registered'] or 0, 
        'total_votes_cast': station_aggr['total_present'] or 0,
        'valid_votes': valid_votes_total, 
        'msp_votes': msp_votes_sum,
        'total_bureaux': total_bureaux, 
        'reported_bureaux': reported_bureaux,
        'turnout_percent': round((station_aggr['total_present'] or 0) / max(station_aggr['total_registered'] or 0, 1) * 100, 1),
        'msp_percent': round(msp_votes_sum / max(valid_votes_total, 1) * 100, 1),
        'completion_percent': round(reported_bureaux / max(total_bureaux, 1) * 100, 1),
    }

    recent_activities = StationResult.objects.filter(bureau__in=bureaux_qs, bureau__is_deleted=False, is_deleted=False).select_related('bureau__commune__wilaya', 'submitted_by').order_by('-submitted_at')[:10]
    participation_rows = StationResult.objects.filter(bureau__in=bureaux_qs, bureau__is_deleted=False, is_deleted=False).annotate(day=TruncDate('submitted_at')).values('day').annotate(total_registered=Sum('registered_voters'), total_present=Sum('total_votes_cast')).order_by('day')
    participation_by_day = {row['day']: row for row in participation_rows if row['day']}
    last_day = max(participation_by_day.keys()) if participation_by_day else timezone.localdate()
    participation_trend = []
    for offset in range(6, -1, -1):
        day = last_day - timedelta(days=offset)
        day_data = participation_by_day.get(day)
        registered = (day_data['total_registered'] or 0) if day_data else 0
        present = (day_data['total_present'] or 0) if day_data else 0
        participation_trend.append({'label': day.strftime('%d/%m'), 'turnout': round((present / registered * 100), 1) if registered else 0})

    wilaya_stats = None
    national_party_totals = {}
    seats_projection = {}
    seats_meta = {}
    total_seats = 0
    total_national_msp_seats = 0

    # ==========================================
    # 1. NATIONAL / SUPER ADMIN LOGIC (CACHED)
    # ==========================================
    if role in ['national', 'super_admin'] and active_election:
        cache_key = f"national_math_{active_election.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            # 🏎️ INSTANT LOAD FROM RAM
            national_party_totals = cached_data['national_party_totals']
            total_national_msp_seats = cached_data['total_national_msp_seats']
            total_seats = cached_data['total_seats']
        else:
            # 🐢 HEAVY LIFTING
            msp_wilaya_subquery = ListResult.objects.filter(
                station_result__bureau__commune__wilaya_id=OuterRef('id'), station_result__bureau__election=active_election,
                station_result__bureau__is_deleted=False, station_result__is_deleted=False, election_list__is_our_party=True
            ).values('station_result__bureau__commune__wilaya_id').annotate(total_msp=Sum('votes')).values('total_msp')

            wilaya_stats = Wilaya.objects.annotate(
                total_bureaux=Count('communes__bureaux', filter=Q(communes__bureaux__election=active_election, communes__bureaux__is_deleted=False), distinct=True),
                reported_bureaux=Count('communes__bureaux', filter=Q(communes__bureaux__election=active_election, communes__bureaux__result__isnull=False, communes__bureaux__result__is_deleted=False, communes__bureaux__is_deleted=False), distinct=True),
                total_votes=Sum('communes__bureaux__result__total_votes_cast', filter=Q(communes__bureaux__election=active_election, communes__bureaux__result__is_deleted=False, communes__bureaux__is_deleted=False)),
                total_null=Sum('communes__bureaux__result__null_votes', filter=Q(communes__bureaux__election=active_election, communes__bureaux__result__is_deleted=False, communes__bureaux__is_deleted=False)),
                msp_votes=Subquery(msp_wilaya_subquery, output_field=IntegerField())
            ).filter(total_bureaux__gt=0).order_by('-reported_bureaux')
            
            all_lists = ElectionList.objects.filter(election=active_election).values('id', 'name_ar', 'is_our_party')
            for lst in all_lists:
                national_party_totals[lst['id']] = {'name': lst['name_ar'], 'is_our_party': lst['is_our_party'], 'total_seats': 0, 'total_votes': 0}

            true_total_seats = sum(w.total_seats for w in wilaya_stats if hasattr(w, 'total_seats') and w.total_seats) or (active_election.total_seats if active_election else 0)
            total_seats = true_total_seats
            msp_list_id = ElectionList.objects.filter(election=active_election, is_our_party=True).values_list('id', flat=True).first()

            for w in wilaya_stats:
                w_valid_votes = max((w.total_votes or 0) - (w.total_null or 0), 0)
                w.msp_percent = round((w.msp_votes or 0) / max(w_valid_votes, 1) * 100, 1)
                
                if w_valid_votes > 0:
                    valid_w_sr = StationResult.objects.filter(bureau__commune__wilaya=w, bureau__election=active_election, bureau__is_deleted=False, is_deleted=False).values_list('id', flat=True)
                    w_list_votes = ListResult.objects.filter(station_result_id__in=valid_w_sr).values('election_list_id').annotate(total=Sum('votes'))
                    w_dict = {item['election_list_id']: item['total'] for item in w_list_votes}
                    w_calc = calculate_seats_allocation(w_valid_votes, w_dict, w.total_seats or 4)
                    w_seats = w_calc['lists']
                    
                    w.msp_seats_won = w_seats.get(msp_list_id, {}).get('seats', 0) if msp_list_id else 0
                    total_national_msp_seats += w.msp_seats_won
                    
                    for list_id, seat_data in w_seats.items():
                        if list_id in national_party_totals:
                            national_party_totals[list_id]['total_seats'] += seat_data.get('seats', 0)
                            national_party_totals[list_id]['total_votes'] += w_dict.get(list_id, 0)
                else:
                    w.msp_seats_won = 0

            national_party_totals = dict(sorted(national_party_totals.items(), key=lambda item: item[1]['total_seats'], reverse=True))
            
            # 💾 SAVE TO CACHE FOR 120 SECONDS
            cache.set(cache_key, {
                'national_party_totals': national_party_totals,
                'total_national_msp_seats': total_national_msp_seats,
                'total_seats': total_seats
            }, timeout=120)

    context = {
        'stats': stats, 'active_election': active_election, 'role': role, 'recent_activities': recent_activities,
        'participation_trend': participation_trend, 'wilaya_stats': wilaya_stats,
        'total_seats': total_seats, 'total_national_msp_seats': total_national_msp_seats,
    }

    if role in ['national', 'super_admin']:
        context['active_page'] = 'dashboard'
        context['national_party_totals'] = national_party_totals
        return render(request, 'dashboard_national.html', context)

    # ==========================================
    # 2. WILAYA ADMIN LOGIC (CACHED)
    # ==========================================
    elif role == 'wilaya':
        context['active_page'] = 'dashboard'
        wilaya = role_obj.wilaya
        context['scope_name'] = f"{wilaya.code} - {wilaya.name_fr}"
        context['wilaya'] = wilaya 
        
        if active_election:
            for c in Commune.objects.filter(wilaya=wilaya):
                BureauDeVote.objects.get_or_create(commune=c, election=active_election, code=f"PV_{c.code}", defaults={'name': f'محضر بلدية {c.name_ar}', 'registered_voters': 0, 'is_deleted': False})

        pv_id_subquery = BureauDeVote.objects.filter(commune_id=OuterRef('id'), election=active_election, code__startswith="PV_", is_deleted=False).values('id')[:1]
        commune_msp_sub = ListResult.objects.filter(
            station_result__bureau__commune_id=OuterRef('id'), station_result__bureau__election=active_election,
            station_result__bureau__is_deleted=False, station_result__is_deleted=False, election_list__is_our_party=True
        ).values('station_result__bureau__commune_id').annotate(total_msp=Sum('votes')).values('total_msp')

        communes_qs = Commune.objects.filter(wilaya=wilaya).select_related('wilaya').annotate(
            total_bureaux=Count('bureaux', filter=Q(bureaux__election=active_election, bureaux__is_deleted=False), distinct=True),
            reported_bureaux=Count('bureaux', filter=Q(bureaux__election=active_election, bureaux__result__isnull=False, bureaux__result__is_deleted=False, bureaux__is_deleted=False), distinct=True),
            msp_votes=Subquery(commune_msp_sub, output_field=IntegerField()),
            pv_id=Subquery(pv_id_subquery, output_field=IntegerField())
        ).order_by('code')
        context['communes'] = communes_qs
        
        # 🚀 PILLAR 2: CACHED SEAT PROJECTION
        total_seats = wilaya.total_seats if hasattr(wilaya, 'total_seats') and wilaya.total_seats else 4
        cache_key = f"wilaya_math_{wilaya.id}_{active_election.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            seats_projection = cached_data['seats_projection']
            seats_meta = cached_data['seats_meta']
            total_seats = cached_data['total_seats']
        else:
            all_list_votes = ListResult.objects.filter(station_result_id__in=valid_sr_ids).values('election_list_id', 'election_list__name_ar', 'election_list__is_our_party').annotate(total_votes=Sum('votes'))
            list_votes_dict = {item['election_list_id']: item['total_votes'] for item in all_list_votes}
            calc_result = calculate_seats_allocation(valid_votes_total, list_votes_dict, total_seats)
            
            seats_projection = calc_result['lists']
            seats_meta = calc_result['meta']
            
            for item in all_list_votes:
                lid = item['election_list_id']
                if lid in seats_projection:
                    seats_projection[lid]['name'] = item['election_list__name_ar']
                    seats_projection[lid]['is_our_party'] = item['election_list__is_our_party']
                    
            cache.set(cache_key, {
                'seats_projection': seats_projection,
                'seats_meta': seats_meta,
                'total_seats': total_seats
            }, timeout=120)

        context['seats_projection'] = seats_projection
        context['seats_meta'] = seats_meta
        context['total_seats'] = total_seats
        return render(request, 'dashboard_wilaya.html', context)

    elif role == 'commune':
        context['active_page'] = 'dashboard'
        
        if not role_obj.commune:
            messages.error(request, "⚠️ رابط البلدية مفقود. يرجى التواصل مع المسؤول الوطني.")
            return redirect('no_role')
            
        commune = role_obj.commune
        context['scope_name'] = f"{commune.name_fr} ({commune.wilaya.name_fr})"
        context['wilaya'] = commune.wilaya 
        
        # ✅ AUTO-CREATE THE SINGLE COMMUNE PV (Clean Slate)
        commune_pv = None
        if active_election:
            # If it was hard-deleted, this will simply create a brand new, fresh one!
            commune_pv, _ = BureauDeVote.objects.get_or_create(
                commune=commune,
                election=active_election,
                code=f"PV_{commune.code}",
                defaults={'name': f'محضر بلدية {commune.name_ar}', 'registered_voters': 0, 'is_deleted': False}
            )
            # Check if it has a valid result to show the correct status in UI
            commune_pv.has_result = StationResult.objects.filter(bureau=commune_pv, is_deleted=False).exists()
            
        context['commune_pv'] = commune_pv
        
        # 📊 Calculate LOCAL Commune Stats (No Seat Math)
        local_stats = {
            'registered_voters': 0,
            'total_votes_cast': 0,
            'valid_votes': 0,
            'msp_votes': 0,
            'turnout_percent': 0.0,
            'msp_percent': 0.0,
            'completion_percent': 0.0
        }
        
        if commune_pv:
            # Get the result for this specific PV
            result = StationResult.objects.filter(bureau=commune_pv, is_deleted=False).first()
            
            if result:
                local_stats['completion_percent'] = 100.0
                local_stats['registered_voters'] = result.registered_voters or 0
                local_stats['total_votes_cast'] = result.total_votes_cast or 0
                local_stats['valid_votes'] = (result.total_votes_cast or 0) - (result.null_votes or 0)
                
                # Get MSP Votes for this specific PV
                msp_list_id = ElectionList.objects.filter(election=active_election, is_our_party=True).values_list('id', flat=True).first()
                if msp_list_id:
                    msp_lr = ListResult.objects.filter(station_result=result, election_list_id=msp_list_id).first()
                    local_stats['msp_votes'] = msp_lr.votes if msp_lr else 0
                    
                # Calculate percentages
                if local_stats['registered_voters'] > 0:
                    local_stats['turnout_percent'] = round((local_stats['total_votes_cast'] / local_stats['registered_voters']) * 100, 1)
                if local_stats['valid_votes'] > 0:
                    local_stats['msp_percent'] = round((local_stats['msp_votes'] / local_stats['valid_votes']) * 100, 1)

        context['stats'] = local_stats
        
        # We DO NOT pass seats_projection or seats_meta to the commune template
        return render(request, 'dashboard_commune.html', context)

    return redirect('no_role')

def no_role_view(request):
    return render(request, 'no_role.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('elections/', include('elections.urls', namespace='elections')),
    path('', dashboard_router, name='home'),
    path('no-role/', no_role_view, name='no_role'),
    path('elections/export/', export_results, name='export_results'),
    path('elections/wilaya/<str:wilaya_code>/', wilaya_detail, name='wilaya_detail'),
    path('users/', include('users.urls', namespace='users')),
]
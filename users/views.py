from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Q
from accounts.models import UserRole
from territories.models import Wilaya, Commune
from django.http import JsonResponse
from territories.models import Commune

User = get_user_model()

def api_communes_by_wilaya(request, wilaya_id):
    """Returns JSON list of communes for a specific wilaya"""
    communes = Commune.objects.filter(wilaya_id=wilaya_id).order_by('name_fr').values('id', 'name_fr', 'name_ar')
    return JsonResponse(list(communes), safe=False)

def _get_role_info(request):
    try:
        role_obj = request.user.role_profile
        return role_obj, role_obj.role
    except AttributeError:
        return None, None

@login_required
def user_list(request):
    role_obj, role = _get_role_info(request)
    if role not in ['national', 'super_admin', 'wilaya']:
        messages.error(request, "غير مصرح لك بإدارة المستخدمين")
        return redirect('home')

    users = User.objects.select_related('role_profile__wilaya', 'role_profile__commune').all()
    
    # Scope the list: Wilaya admins only see commune users in their wilaya
    if role == 'wilaya':
        users = users.filter(role_profile__role='commune', role_profile__commune__wilaya=role_obj.wilaya)
        
    role_filter = request.GET.get('role', '')
    search = request.GET.get('search', '')
    
    if role_filter:
        users = users.filter(role_profile__role=role_filter)
    if search:
        users = users.filter(Q(email__icontains=search) | Q(full_name__icontains=search))

    return render(request, 'users/list.html', {
        'users': users, 'role_filter': role_filter, 'search': search,
        'active_page': 'users', 'current_role': role
    })

@login_required
def user_create(request):
    role_obj, role = _get_role_info(request)
    if role not in ['national', 'super_admin', 'wilaya']:
        messages.error(request, "غير مصرح لك")
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '')
        target_role = request.POST.get('role', '')
        wilaya_id = request.POST.get('wilaya_id')
        commune_id = request.POST.get('commune_id')
        is_active = request.POST.get('is_active') == 'on'

        # Wilaya admin restrictions
        if role == 'wilaya':
            if target_role != 'commune':
                messages.error(request, "يمكنك فقط إضافة ممثلي البلديات")
                return redirect('users:create')
            wilaya_id = str(role_obj.wilaya.id) # Force their wilaya

        if not all([email, full_name, password, target_role]):
            messages.error(request, "يرجى ملء جميع الحقول المطلوبة")
            return redirect('users:create')

        if User.objects.filter(email=email).exists():
            messages.error(request, "البريد الإلكتروني مستخدم بالفعل")
            return redirect('users:create')

        if target_role in ['wilaya', 'commune'] and not wilaya_id:
            messages.error(request, "يجب تحديد الولاية")
            return redirect('users:create')
        if target_role == 'commune' and not commune_id:
            messages.error(request, "يجب تحديد البلدية")
            return redirect('users:create')

        user = User.objects.create_user(email=email, full_name=full_name, password=password, is_active=is_active)
        
        wilaya = Wilaya.objects.filter(id=wilaya_id).first() if wilaya_id else None
        commune = Commune.objects.filter(id=commune_id).first() if commune_id else None

        UserRole.objects.create(user=user, role=target_role, wilaya=wilaya, commune=commune)
        messages.success(request, f" تم إنشاء حساب {full_name} بنجاح")
        return redirect('users:list')

    # Context setup based on role
    if role == 'wilaya':
        wilayas = Wilaya.objects.filter(id=role_obj.wilaya.id)
        communes = Commune.objects.filter(wilaya=role_obj.wilaya).order_by('code')
        allowed_roles = [('commune', 'ممثل بلدية')]
    else:
        wilayas = Wilaya.objects.all().order_by('code')
        communes = Commune.objects.select_related('wilaya').order_by('wilaya__code', 'code')
        allowed_roles = [
            ('national', 'مسؤول وطني'), ('super_admin', 'مطور النظام (Super Admin)'),
            ('wilaya', 'ممثل ولاية'), ('commune', 'ممثل بلدية')
        ]

    return render(request, 'users/create_edit.html', {
        'form_type': 'create', 'wilayas': wilayas, 'communes': communes,
        'allowed_roles': allowed_roles, 'active_page': 'users', 'current_role': role
    })

@login_required
def user_edit(request, user_id):
    role_obj, role = _get_role_info(request)
    if role not in ['national', 'super_admin', 'wilaya']:
        return redirect('home')

    target_user = get_object_or_404(User, id=user_id)
    target_profile = getattr(target_user, 'role_profile', None)
    target_role = target_profile.role if target_profile else ''

    # Block Wilaya admins from editing outside their scope
    if role == 'wilaya':
        if target_role != 'commune' or (target_profile and target_profile.commune.wilaya != role_obj.wilaya):
            messages.error(request, "لا يمكنك تعديل هذا المستخدم")
            return redirect('users:list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '')
        new_target_role = request.POST.get('role', '')
        wilaya_id = request.POST.get('wilaya_id')
        commune_id = request.POST.get('commune_id')
        is_active = request.POST.get('is_active') == 'on'

        if role == 'wilaya':
            new_target_role = 'commune'
            wilaya_id = str(role_obj.wilaya.id)

        target_user.email = email
        target_user.full_name = full_name
        target_user.is_active = is_active
        if password: target_user.set_password(password)
        target_user.save()

        if target_profile:
            target_profile.role = new_target_role
            target_profile.wilaya_id = wilaya_id if wilaya_id else None
            target_profile.commune_id = commune_id if commune_id else None
            target_profile.save()
        else:
            wilaya = Wilaya.objects.filter(id=wilaya_id).first() if wilaya_id else None
            commune = Commune.objects.filter(id=commune_id).first() if commune_id else None
            UserRole.objects.create(user=target_user, role=new_target_role, wilaya=wilaya, commune=commune)

        messages.success(request, f" تم تحديث بيانات {full_name} بنجاح")
        return redirect('users:list')

    if role == 'wilaya':
        wilayas = Wilaya.objects.filter(id=role_obj.wilaya.id)
        communes = Commune.objects.filter(wilaya=role_obj.wilaya).order_by('code')
        allowed_roles = [('commune', 'ممثل بلدية')]
    else:
        wilayas = Wilaya.objects.all().order_by('code')
        communes = Commune.objects.select_related('wilaya').order_by('wilaya__code', 'code')
        allowed_roles = [
            ('national', 'مسؤول وطني'), ('super_admin', 'مطور النظام (Super Admin)'),
            ('wilaya', 'ممثل ولاية'), ('commune', 'ممثل بلدية')
        ]

    return render(request, 'users/create_edit.html', {
        'form_type': 'edit', 'user': target_user, 'role_profile': target_profile,
        'wilayas': wilayas, 'communes': communes, 'allowed_roles': allowed_roles,
        'active_page': 'users', 'current_role': role
    })

@login_required
def user_delete(request, user_id):
    role_obj, role = _get_role_info(request)
    if role not in ['national', 'super_admin', 'wilaya']:
        return redirect('home')

    target_user = get_object_or_404(User, id=user_id)
    target_profile = getattr(target_user, 'role_profile', None)
    target_role = target_profile.role if target_profile else ''

    # 🔒 STRICT DELETION RULES
    if request.user == target_user:
        messages.error(request, "لا يمكنك حذف حسابك الخاص")
        return redirect('users:list')
    if target_role == 'super_admin':
        messages.error(request, " لا يمكن حذف حساب المطور الرئيسي (Super Admin)")
        return redirect('users:list')
    if role == 'national' and target_role == 'national':
        messages.error(request, "لا يمكن للمسؤول الوطني حذف مسؤول وطني آخر")
        return redirect('users:list')
    if role == 'wilaya':
        if target_role != 'commune' or target_profile.commune.wilaya != role_obj.wilaya:
            messages.error(request, "لا يمكنك سوى حذف ممثلي البلديات التابعة لولايتك")
            return redirect('users:list')

    if request.method == 'POST':
        name = target_user.full_name or target_user.email
        target_user.delete()
        messages.success(request, f" تم حذف المستخدم '{name}' بنجاح")
        return redirect('users:list')

    return render(request, 'users/delete_confirm.html', {'user': target_user, 'active_page': 'users'})
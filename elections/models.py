from django.db import models
from django.conf import settings
from territories.models import Commune, Wilaya
from django.utils import timezone

class Election(models.Model):
    TYPE_CHOICES = [
        ('presidential', 'Presidential'),
        ('legislative', 'Legislative'),
        ('local_apc', 'Local (APC)'),
        ('local_apw', 'Local (APW)'),
        ('referendum', 'Referendum'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    name_ar = models.CharField(max_length=255)
    name_fr = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    election_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_seats = models.IntegerField(default=4, verbose_name="عدد المقاعد المخصصة", help_text="عدد المقاعد المتنافس عليها في هذا الانتخاب")

    class Meta:
        # 🚀 PILLAR 1: Index for fast lookup of active elections
        indexes = [
            models.Index(fields=['status', '-election_date']),
        ]

    def __str__(self):
        return f"{self.name_fr} ({self.get_type_display()})"


class ElectionList(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='lists')
    name_ar = models.CharField(max_length=255, verbose_name="اسم القائمة / الحزب")
    name_fr = models.CharField(max_length=255, blank=True, null=True, verbose_name="اسم القائمة (فرنسي) - اختياري")
    is_our_party = models.BooleanField(default=False, verbose_name="هل هي قائمة الحركة (MSP)؟", help_text="Check ONLY for MSP")
    display_order = models.SmallIntegerField(default=0, verbose_name="ترتيب العرض")
    wilaya = models.ForeignKey(
            Wilaya, on_delete=models.CASCADE, null=True, blank=True, 
            related_name='local_lists', verbose_name="الولاية (للقوائم الحرة فقط)",
            help_text="اتركه فارغاً إذا كانت قائمة وطنية / حزب رسمي"
        )
    is_active = models.BooleanField(default=True, verbose_name="نشط (يظهر في الاستمارات)")

    class Meta:
        unique_together = ('election', 'name_ar', 'wilaya')
        ordering = ['display_order']
        verbose_name = "قائمة انتخابية"
        verbose_name_plural = "القوائم الانتخابية"
        # 🚀 PILLAR 1: Index for fast MSP vote filtering
        indexes = [
            models.Index(fields=['election', 'is_our_party']),
        ]

    def __str__(self):
        return self.name_ar


class BureauDeVote(models.Model):
    commune = models.ForeignKey(Commune, on_delete=models.RESTRICT, related_name='bureaux')
    election = models.ForeignKey(Election, on_delete=models.RESTRICT, related_name='bureaux')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255, blank=True, null=True)
    registered_voters = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('commune', 'election', 'code')
        verbose_name = "مركز تصويت"
        verbose_name_plural = "محاضر التصويت"
        # 🚀 PILLAR 1: Composite indexes for heavy dashboard filtering
        indexes = [
            models.Index(fields=['is_deleted', 'election']),
            models.Index(fields=['commune', 'is_deleted']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.name or self.code} ({self.commune.wilaya.code})"


class StationResult(models.Model):
    election = models.ForeignKey(Election, on_delete=models.RESTRICT)
    bureau = models.OneToOneField(BureauDeVote, on_delete=models.RESTRICT, related_name='result')
    
    registered_voters = models.IntegerField()
    total_votes_cast = models.IntegerField()
    null_votes = models.IntegerField(default=0)
    blank_votes = models.IntegerField(default=0)
    
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_results')
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    last_edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_results')
    last_edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 🚀 PILLAR 1: Indexes for bulletproof aggregation queries
        indexes = [
            models.Index(fields=['bureau', 'is_deleted']),
            models.Index(fields=['election', 'is_deleted']),
            models.Index(fields=['-submitted_at']), # Speeds up "Recent Activities"
        ]

    def __str__(self):
        return f"Result for {self.bureau}"


class ListResult(models.Model):
    station_result = models.ForeignKey(StationResult, on_delete=models.CASCADE, related_name='list_results')
    election_list = models.ForeignKey(ElectionList, on_delete=models.RESTRICT)
    votes = models.IntegerField(default=0)

    class Meta:
        unique_together = ('station_result', 'election_list')
        # 🚀 PILLAR 1: Index for fast vote summation
        indexes = [
            models.Index(fields=['station_result', 'election_list']),
        ]


class ResultAuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'إضافة'),
        ('update', 'تعديل'),
        ('delete', 'حذف'),
    ]
    
    table_name = models.CharField(max_length=100, verbose_name="الجدول")
    record_id = models.CharField(max_length=50, verbose_name="رقم السجل") 
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="العملية")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="المستخدم")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="الوقت")
    old_values = models.JSONField(blank=True, null=True, verbose_name="القيم القديمة")
    new_values = models.JSONField(blank=True, null=True, verbose_name="القيم الجديدة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "سجل تدقيق"
        verbose_name_plural = "سجلات التدقيق"
        # 🚀 PILLAR 1: Indexes for fast audit log filtering
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['table_name']),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.table_name} #{self.record_id}"
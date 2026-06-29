from django.db import models

class Wilaya(models.Model):
    code = models.SmallIntegerField(unique=True, verbose_name="Code (01-69)")
    name_ar = models.CharField(max_length=100, verbose_name="Name (AR)")
    name_fr = models.CharField(max_length=100, verbose_name="Name (FR)")
    total_seats = models.IntegerField(default=4, verbose_name="عدد المقاعد المخصصة")

    class Meta:
        ordering = ['code']
        verbose_name_plural = "Wilayas"

    def __str__(self):
        return f"{self.code:02d} - {self.name_fr}"


class Commune(models.Model):
    wilaya = models.ForeignKey(Wilaya, on_delete=models.RESTRICT, related_name='communes')
    code = models.CharField(max_length=10, verbose_name="Code (e.g., 16001)")
    name_ar = models.CharField(max_length=100, verbose_name="Name (AR)")
    name_fr = models.CharField(max_length=100, verbose_name="Name (FR)")

    class Meta:
        unique_together = ('wilaya', 'code')
        ordering = ['wilaya__code', 'code']

    def __str__(self):
        return f"{self.name_fr} ({self.wilaya.code})"


class CommuneSettings(models.Model):
    commune = models.OneToOneField(Commune, on_delete=models.CASCADE, related_name='settings')
    allow_bureau_creation = models.BooleanField(default=False)

    def __str__(self):
        return f"Settings for {self.commune}"
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name='Email Address')
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    LANGUAGE_CHOICES = [('ar', 'Arabic'), ('fr', 'French')]
    language_pref = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='fr')

    is_staff = models.BooleanField(default=False) # Allows access to Django Admin
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email' # This forces login via Email!
    REQUIRED_FIELDS = ['full_name']
    objects = CustomUserManager()

    def __str__(self):
        return self.email

class UserRole(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('national', 'National Executive'),
        ('wilaya', 'Wilaya Representative'),
        ('commune', 'Commune Representative'),
    ]
    
    # Spec 4.7: Strictly one role per user
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='role_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Scopes
    wilaya = models.ForeignKey('territories.Wilaya', on_delete=models.SET_NULL, null=True, blank=True)
    commune = models.ForeignKey('territories.Commune', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "User Role & Scope"
        verbose_name_plural = "User Roles & Scopes"

    def __str__(self):
        return f"{self.user.email} - {self.get_role_display()}"
        
    def clean(self):
        # Spec 3.2: Strict Scope Rules Validation
        if self.role == 'wilaya' and not self.wilaya:
            raise ValidationError('Wilaya representatives must be assigned to a Wilaya.')
        if self.role == 'commune' and not self.commune:
            raise ValidationError('Commune representatives must be assigned to a Commune.')
        if self.role in ('national', 'super_admin') and (self.wilaya or self.commune):
            raise ValidationError('National and Super Admins cannot have territorial scopes.')
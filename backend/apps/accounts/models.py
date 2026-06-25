from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        CLIENT = 'client', _('Client')
        PROVIDER = 'provider', _('Provider')
        ADMIN = 'admin', _('Admin')
        
    email = models.EmailField(_('email address'), unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True) # Not unique, validation in logic
    username = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CLIENT)
    
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    
    language = models.CharField(max_length=5, default='ru')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class ProviderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='provider_profile')
    bio = models.TextField(blank=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    reviews_count = models.IntegerField(default=0)
    is_blocked = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Provider Profile for {self.user.email}"

class Availability(models.Model):
    STATUS_CHOICES = (
        ('busy', _('Busy (Order)')),
        ('blocked', _('Blocked (Manual)')),
    )
    
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='availabilities')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='blocked')
    order = models.OneToOneField(
        'marketplace.Order', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='availability_slot'
    )
    
    class Meta:
        ordering = ['start_at']
        indexes = [
            models.Index(fields=['provider', 'start_at', 'end_at']),
        ]
        verbose_name = _('Availability Slot')
        verbose_name_plural = _('Availability Slots')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValidationError(_("End time must be after start time."))
        
        # Check overlaps
        # overlap if (StartA <= EndB) and (EndA >= StartB)
        qs = Availability.objects.filter(
            provider=self.provider,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
            
        if qs.exists():
            raise ValidationError(_("This time slot overlaps with an existing one."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.provider.user.email} - {self.start_at} to {self.end_at} ({self.status})"

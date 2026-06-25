from rest_framework import serializers
from .models import Report

class ReportSerializer(serializers.ModelSerializer):
    reporter_email = serializers.EmailField(source='reporter.email', read_only=True)
    object_summary = serializers.SerializerMethodField()
    object_missing = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'id', 'reporter', 'reporter_email', 'content_type', 'object_id', 
            'reason', 'message', 'status', 'created_at', 'resolution_note',
            'object_summary', 'object_missing'
        )
        read_only_fields = ('reporter', 'status', 'created_at', 'resolution_note')

    def get_object_summary(self, obj):
        from apps.catalog.models import Service
        from apps.accounts.models import ProviderProfile
        from apps.marketplace.models import Review
        from apps.comments.models import ServiceComment

        models_map = {
            Report.ContentType.PROVIDER: ProviderProfile,
            Report.ContentType.SERVICE: Service,
            Report.ContentType.REVIEW: Review,
            Report.ContentType.COMMENT: ServiceComment
        }
        
        model = models_map.get(obj.content_type)
        if not model:
            return None
            
        instance = model.objects.filter(id=obj.object_id).first()
        if not instance:
            return None
            
        # Basic summary logic
        if obj.content_type == Report.ContentType.PROVIDER:
            return f"Provider: {instance.user.email}"
        elif obj.content_type == Report.ContentType.SERVICE:
            return f"Service: {instance.title}"
        elif obj.content_type == Report.ContentType.REVIEW:
            return f"Review rating: {instance.rating}"
        elif obj.content_type == Report.ContentType.COMMENT:
            return f"Comment text: {instance.text[:30]}..."
        return str(instance)

    def get_object_missing(self, obj):
        from apps.catalog.models import Service
        from apps.accounts.models import ProviderProfile
        from apps.marketplace.models import Review
        from apps.comments.models import ServiceComment

        models_map = {
            Report.ContentType.PROVIDER: ProviderProfile,
            Report.ContentType.SERVICE: Service,
            Report.ContentType.REVIEW: Review,
            Report.ContentType.COMMENT: ServiceComment
        }
        
        model = models_map.get(obj.content_type)
        if not model:
            return True
        return not model.objects.filter(id=obj.object_id).exists()

    def validate(self, data):
        user = self.context['request'].user
        content_type = data['content_type']
        object_id = data['object_id']

        # 1. Self-report check
        from apps.catalog.models import Service
        from apps.accounts.models import ProviderProfile
        from apps.marketplace.models import Review
        from apps.comments.models import ServiceComment

        if content_type == Report.ContentType.PROVIDER:
            if not ProviderProfile.objects.filter(id=object_id).exists():
                raise serializers.ValidationError("Provider not found.")
            if ProviderProfile.objects.filter(id=object_id, user=user).exists():
                raise serializers.ValidationError("Cannot report yourself.")
        
        elif content_type == Report.ContentType.SERVICE:
            if not Service.objects.filter(id=object_id).exists():
                raise serializers.ValidationError("Service not found.")
            if Service.objects.filter(id=object_id, provider__user=user).exists():
                raise serializers.ValidationError("Cannot report your own service.")
        
        elif content_type == Report.ContentType.REVIEW:
            if not Review.objects.filter(id=object_id).exists():
                raise serializers.ValidationError("Review not found.")
            if Review.objects.filter(id=object_id, client=user).exists():
                raise serializers.ValidationError("Cannot report your own review.")
        
        elif content_type == Report.ContentType.COMMENT:
            if not ServiceComment.objects.filter(id=object_id).exists():
                raise serializers.ValidationError("Comment not found.")
            if ServiceComment.objects.filter(id=object_id, user=user).exists():
                raise serializers.ValidationError("Cannot report your own comment.")

        # 2. Duplicate active report check
        if Report.objects.filter(
            reporter=user, 
            content_type=content_type, 
            object_id=object_id,
            status__in=[Report.Status.OPEN, Report.Status.IN_REVIEW]
        ).exists():
            raise serializers.ValidationError("You already have an active report for this object.")

        return data

class ReportResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ('resolution_note',)
        required_fields = ('resolution_note',)

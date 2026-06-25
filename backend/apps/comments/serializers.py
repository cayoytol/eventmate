from rest_framework import serializers
from .models import ServiceComment

class ServiceCommentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    replies = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_reply = serializers.SerializerMethodField()

    class Meta:
        model = ServiceComment
        fields = (
            'id', 'service', 'user', 'user_email', 'username', 
            'text', 'parent', 'is_deleted', 'created_at', 'updated_at',
            'replies', 'can_edit', 'can_reply'
        )
        read_only_fields = ('user', 'service', 'is_deleted', 'created_at', 'updated_at')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.is_deleted:
            ret['text'] = "[deleted]"
        return ret

    def get_replies(self, obj):
        if obj.parent_id is not None:
            # Prevent infinite recursion, only depth 1
            return []
        
        # Prefetched in view for efficiency
        replies = obj.replies.all()
        return ServiceCommentSerializer(replies, many=True, context=self.context).data

    def validate_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Comment text cannot be empty.")
        return value.strip()

    def validate_parent(self, value):
        if value is not None:
            if value.parent_id is not None:
                raise serializers.ValidationError("Cannot reply to a reply. Maximum depth is 1.")
            
            # Parent comment must belong to same service
            view = self.context.get('view')
            if view and hasattr(view, 'kwargs'):
                service_id = view.kwargs.get('service_id')
                if service_id and value.service_id != int(service_id):
                    raise serializers.ValidationError("Parent comment belongs to a different service.")
        return value

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.is_deleted:
            return False
        # Author can edit
        if obj.user_id == request.user.id:
            # Root comment can only be edited if it has no replies (per view logic)
            if obj.parent_id is None:
                return not obj.replies.exists()
            return True
        return False

    def get_can_reply(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.is_deleted:
            return False
        # Only reply to root comments (depth 1 max)
        if obj.parent_id is not None:
            return False
        # Only the provider owner of the service can reply to comments
        service = obj.service
        return service.provider.user_id == request.user.id

from rest_framework import serializers

class RequestAssistantSerializer(serializers.Serializer):
    category = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    event_date = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    budget = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    draft = serializers.CharField(max_length=1500, required=False, allow_blank=True, default="")
    locale = serializers.ChoiceField(choices=[('ru', 'ru'), ('en', 'en'), ('kz', 'kz')], default='ru')

    def validate(self, attrs):
        # Ensure at least category or draft has some text
        category = attrs.get('category', '').strip()
        draft = attrs.get('draft', '').strip()
        if not category and not draft:
            raise serializers.ValidationError("Either category or draft must be provided to generate a suggestion.")
        return attrs


class OfferAssistantSerializer(serializers.Serializer):
    request_description = serializers.CharField(max_length=1500, required=True, allow_blank=False)
    service_title = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    price = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    locale = serializers.ChoiceField(choices=[('ru', 'ru'), ('en', 'en'), ('kz', 'kz')], default='ru')

    def validate_request_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Request description cannot be blank.")
        return value.strip()

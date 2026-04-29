from rest_framework import serializers

from care_ai.agent.schema import InvalidResponseSchema, validate_response_schema
from care_ai.settings import plugin_settings


class AskRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    model = serializers.CharField(required=False)
    response_schema = serializers.JSONField(required=False, allow_null=True)
    max_tool_iterations = serializers.IntegerField(required=False, min_value=1, max_value=25)

    def validate_prompt(self, value: str) -> str:
        max_chars = plugin_settings.CARE_AI_PROMPT_MAX_CHARS
        if len(value) > max_chars:
            raise serializers.ValidationError(f"prompt exceeds {max_chars} characters")
        return value

    def validate_model(self, value: str) -> str:
        allowed = plugin_settings.CARE_AI_ALLOWED_MODELS
        if value not in allowed:
            raise serializers.ValidationError(f"model must be one of {allowed}")
        return value

    def validate_response_schema(self, value):
        if value in (None, {}):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("response_schema must be a JSON object")
        try:
            validate_response_schema(value)
        except InvalidResponseSchema as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        result.setdefault("model", plugin_settings.CARE_AI_DEFAULT_MODEL)
        result.setdefault("max_tool_iterations", plugin_settings.CARE_AI_MAX_TOOL_ITERATIONS)
        result.setdefault("response_schema", None)
        return result

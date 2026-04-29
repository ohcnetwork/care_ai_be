import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care.emr.models import Encounter

from care_ai.agent.runner import run_ask
from care_ai.permissions import authorize_encounter_read
from care_ai.serializers import AskRequestSerializer

logger = logging.getLogger("care_ai.views")


class AskAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, encounter_external_id):
        serializer = AskRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data

        encounter = get_object_or_404(
            Encounter.objects.select_related("patient"),
            external_id=encounter_external_id,
        )
        authorize_encounter_read(request.user, encounter)

        try:
            result = run_ask(
                encounter=encounter,
                prompt=body["prompt"],
                model=body["model"],
                response_schema=body["response_schema"],
                max_iterations=body["max_tool_iterations"],
            )
        except Exception as exc:
            return _map_runner_error(exc)

        return Response(
            {
                "output": result.output,
                "model": result.model,
                "usage": result.usage,
                "tool_calls": result.tool_calls,
                "duration_ms": result.duration_ms,
            }
        )


def _map_runner_error(exc: Exception) -> Response:
    name = type(exc).__name__
    msg = str(exc)
    logger.exception("agent run failed: %s", name)

    if name == "MaxTurnsExceeded":
        return Response(
            {"error": "max_tool_iterations exceeded", "detail": msg},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    if name in {"APITimeoutError", "Timeout"}:
        return Response(
            {"error": "upstream timeout", "detail": msg},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    if name == "RateLimitError":
        return Response(
            {"error": "rate limited by openai", "detail": msg},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return Response(
        {"error": "agent run failed", "detail": msg},
        status=status.HTTP_502_BAD_GATEWAY,
    )

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from agents import Agent, Runner

from care_ai.agent.context import PatientContext
from care_ai.agent.schema import json_schema_to_pydantic
from care_ai.agent.tools import ALL_TOOLS
from care_ai.settings import plugin_settings

logger = logging.getLogger("care_ai.runner")


@dataclass
class AskResult:
    output: Any
    model: str
    usage: dict
    tool_calls: list[dict]
    duration_ms: int


def run_ask(
    *,
    encounter,
    prompt: str,
    model: str,
    response_schema: dict | None,
    max_iterations: int,
) -> AskResult:
    os.environ.setdefault("OPENAI_API_KEY", plugin_settings.CARE_AI_OPENAI_API_KEY)

    ctx = PatientContext(
        patient_id=encounter.patient.external_id,
        current_encounter_id=encounter.external_id,
    )
    output_type = json_schema_to_pydantic(response_schema)

    agent = Agent(
        name="care-clinical-assistant",
        instructions=plugin_settings.CARE_AI_SYSTEM_PROMPT,
        model=model,
        tools=ALL_TOOLS,
        output_type=output_type,
    )

    started = time.monotonic()
    result = Runner.run_sync(
        agent,
        prompt,
        context=ctx,
        max_turns=max_iterations,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    return AskResult(
        output=_unwrap_output(result.final_output),
        model=model,
        usage=_extract_usage(result),
        tool_calls=_extract_tool_calls(result),
        duration_ms=duration_ms,
    )


def _unwrap_output(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _extract_usage(result) -> dict:
    try:
        usage = result.context_wrapper.usage
        if hasattr(usage, "model_dump"):
            return usage.model_dump()
        return {k: v for k, v in usage.__dict__.items() if not k.startswith("_")}
    except Exception:
        logger.warning("could not extract usage from RunResult", exc_info=True)
        return {}


def _extract_tool_calls(result) -> list[dict]:
    calls: list[dict] = []
    try:
        for item in getattr(result, "new_items", []):
            tool_call = getattr(item, "tool_call", None) or getattr(item, "raw_item", None)
            name = getattr(tool_call, "name", None) or getattr(tool_call, "tool_name", None)
            if name:
                calls.append(
                    {
                        "name": name,
                        "arguments": getattr(tool_call, "arguments", None),
                    }
                )
    except Exception:
        logger.warning("could not extract tool_calls from RunResult", exc_info=True)
    return calls

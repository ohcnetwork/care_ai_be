from typing import Any

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver
from rest_framework.settings import perform_import

from care_ai.apps import PLUGIN_NAME

env = environ.Env()


DEFAULT_SYSTEM_PROMPT = """\
You are a clinical decision-support assistant embedded in CARE, an EMR system.
You are helping a clinician working on a specific patient encounter.

Rules:
- Use the provided tools to look up patient data before answering. Never guess clinical facts.
- The tools are scoped to the current patient; you do not need to (and cannot) supply patient or encounter ids.
- Prefer calling multiple tools in parallel when their results are independent.
- Be concise. Use clinical shorthand the clinician will recognize.
- When uncertain, say so and recommend what the clinician should verify directly.
- Do not provide a final diagnosis or prescribe treatment. Surface findings, flag risks,
  and suggest considerations. The clinician makes the decision.
- If the user's question is outside the scope of the patient's record, say so plainly
  rather than fabricating context.
"""


class PluginSettings:
    def __init__(
        self,
        plugin_name: str = None,
        defaults: dict | None = None,
        import_strings: set | None = None,
        required_settings: set | None = None,
    ) -> None:
        if not plugin_name:
            raise ValueError("Plugin name must be provided")
        self.plugin_name = plugin_name
        self.defaults = defaults or {}
        self.import_strings = import_strings or set()
        self.required_settings = required_settings or set()
        self._cached_attrs = set()
        self.validate()

    def __getattr__(self, attr) -> Any:
        if attr not in self.defaults:
            raise AttributeError("Invalid setting: '%s'" % attr)
        val = self.defaults[attr]
        try:
            val = self.user_settings[attr]
        except KeyError:
            try:
                val = env(attr, cast=type(val))
            except environ.ImproperlyConfigured:
                pass
        if attr in self.import_strings:
            val = perform_import(val, attr)
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    @property
    def user_settings(self) -> dict:
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "PLUGIN_CONFIGS", {}).get(self.plugin_name, {})
        return self._user_settings

    def validate(self) -> None:
        for setting in self.required_settings:
            if not getattr(self, setting):
                raise ImproperlyConfigured(
                    f'The "{setting}" setting is required. '
                    f'Please set the "{setting}" in the environment or the {PLUGIN_NAME} plugin config.'
                )

    def reload(self) -> None:
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


DEFAULTS = {
    "CARE_AI_OPENAI_API_KEY": "",
    "CARE_AI_DEFAULT_MODEL": "gpt-5.4-mini",
    "CARE_AI_ALLOWED_MODELS": ["gpt-5.4-mini", "gpt-5.4", "gpt-4.1", "gpt-4.1-mini"],
    "CARE_AI_MAX_TOOL_ITERATIONS": 10,
    "CARE_AI_REQUEST_TIMEOUT_SECONDS": 60,
    "CARE_AI_SYSTEM_PROMPT": DEFAULT_SYSTEM_PROMPT,
    "CARE_AI_OBSERVATION_ROW_LIMIT": 200,
    "CARE_AI_ENCOUNTER_ROW_LIMIT": 50,
    "CARE_AI_PROMPT_MAX_CHARS": 8000,
}

REQUIRED_SETTINGS = {"CARE_AI_OPENAI_API_KEY"}

plugin_settings = PluginSettings(PLUGIN_NAME, defaults=DEFAULTS, required_settings=REQUIRED_SETTINGS)


@receiver(setting_changed)
def reload_plugin_settings(*args, **kwargs) -> None:
    setting = kwargs["setting"]
    if setting == "PLUGIN_CONFIGS":
        plugin_settings.reload()

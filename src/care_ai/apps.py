from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "care_ai"


class CareAIConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Care AI")

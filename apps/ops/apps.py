"""Installable metadata for the ops App."""

from oldman.apps import AppConfig
from oldman.i18n import gettext_lazy as _

from apps.ops.settings import OpsSettings


class OpsAppConfig(AppConfig[OpsSettings]):
    """Describe the ops App."""

    label = "ops"
    display_name = _("运维")
    icon = "ri-tools-line"
    settings_model = OpsSettings


app = OpsAppConfig()

__all__ = ["OpsAppConfig", "app"]

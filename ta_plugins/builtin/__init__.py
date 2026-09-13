"""Built-in example plugins for ta_plugins."""

from .custom_instructions import custom_instructions_plugin
from .fred_skill_pack import fred_skill_pack_plugin
from .prompt_prefix import prompt_prefix_plugin

__all__ = [
    "custom_instructions_plugin",
    "fred_skill_pack_plugin",
    "prompt_prefix_plugin",
]

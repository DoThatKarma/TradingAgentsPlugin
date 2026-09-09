"""Built-in example plugins for ta_plugins."""

from .custom_instructions import custom_instructions_plugin
from .prompt_prefix import prompt_prefix_plugin

__all__ = ["custom_instructions_plugin", "prompt_prefix_plugin"]

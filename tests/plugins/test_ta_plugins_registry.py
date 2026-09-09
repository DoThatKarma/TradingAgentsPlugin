import pytest

from ta_plugins import Plugin, get_registry, register


def setup_function(function):
    get_registry().clear()


def teardown_function(function):
    get_registry().clear()


def test_register_and_get():
    plugin = Plugin(name="alpha")
    register(plugin)
    assert get_registry().get("alpha") is plugin


def test_duplicate_name_rejected():
    register(Plugin(name="dupe"))
    with pytest.raises(ValueError):
        register(Plugin(name="dupe"))


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        register(Plugin(name=""))


def test_non_plugin_rejected():
    with pytest.raises(TypeError):
        register("not-a-plugin")

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


@pytest.mark.parametrize(
    "bad_name",
    ["", "UPPER", "has space", "slash/name", "a" * 65, "_leading", "x\n"],
)
def test_invalid_names_rejected(bad_name):
    with pytest.raises(ValueError):
        register(Plugin(name=bad_name))


def test_dotted_builtin_style_name_allowed():
    plugin = register(Plugin(name="builtin.custom_instructions"))
    assert get_registry().get("builtin.custom_instructions") is plugin


def test_non_plugin_rejected():
    with pytest.raises(TypeError):
        register("not-a-plugin")

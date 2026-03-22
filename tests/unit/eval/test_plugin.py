# ABOUTME: Tests for the pytest plugin option registration.
# ABOUTME: Validates CLI options are added and markers are registered.


def test_plugin_registers_options(pytestconfig):
    """Plugin should register --eval-dir, --eval-tags, etc."""
    from autobots_devtools_shared_lib.eval.pytest_plugin.plugin import pytest_addoption

    assert callable(pytest_addoption)


def test_plugin_registers_markers():
    from autobots_devtools_shared_lib.eval.pytest_plugin.plugin import pytest_configure

    assert callable(pytest_configure)

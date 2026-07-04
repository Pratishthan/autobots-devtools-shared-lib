# ABOUTME: Unit tests for the dynagent public API surface.
# ABOUTME: Verifies the deep-agent engine symbols are exported.


def test_deep_engine_symbols_exported():
    import autobots_devtools_shared_lib.dynagent as pkg

    for name in ("create_base_deepagent", "DynaDeepAgent", "invoke_deepagent", "ainvoke_deepagent"):
        assert name in pkg.__all__
        assert getattr(pkg, name) is not None

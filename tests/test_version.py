def test_version() -> None:
    try:
        import base_loom_server.version
    except ImportError:
        raise AssertionError("version file not found")

    assert base_loom_server.version.__all__ == ["__version__"]
    assert isinstance(base_loom_server.version.__version__, str)

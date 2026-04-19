"""Pre-Day-1 smoke test so CI has something to collect against the stub scaffold."""


def test_package_imports() -> None:
    """The top-level `efterlev` package imports cleanly on the configured Python."""
    import efterlev

    assert efterlev is not None

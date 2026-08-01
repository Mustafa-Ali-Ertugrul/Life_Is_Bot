def test_adapter_imports_without_circular_error() -> None:
    import app.scheduler.engine
    import app.scheduler.jobs
    import app.scheduler.setup
    import app.tgbot.adapter

    assert app.tgbot.adapter is not None
    assert app.scheduler.engine is not None
    assert app.scheduler.jobs is not None
    assert app.scheduler.setup is not None

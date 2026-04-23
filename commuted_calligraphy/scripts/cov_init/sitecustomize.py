import importlib.util

if importlib.util.find_spec("coverage") is not None:
    import coverage

    coverage.process_startup()

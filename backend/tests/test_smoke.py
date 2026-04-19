def test_pytest_runs():
    assert 1 + 1 == 2


def test_asyncio_mode_works():
    import asyncio
    async def inner():
        return 42
    assert asyncio.run(inner()) == 42

import pytest

from donna_core.tools.results import ExpiredResult, ResultRegistry, UnknownResult


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_register_and_resolve() -> None:
    reg = ResultRegistry()
    entry = reg.register("file", "a.pdf", target=r"C:\a.pdf", subtitle=r"C:\\")
    assert entry.id == "r_1"
    assert reg.resolve("r_1").target == r"C:\a.pdf"


def test_ids_are_unique() -> None:
    reg = ResultRegistry()
    ids = {reg.register("file", str(i), target=str(i)).id for i in range(10)}
    assert len(ids) == 10


def test_unknown_result() -> None:
    with pytest.raises(UnknownResult):
        ResultRegistry().resolve("r_999")


def test_expired_result() -> None:
    clock = FakeClock()
    reg = ResultRegistry(ttl_s=60, clock=clock)
    entry = reg.register("web", "page", target="https://example.com")
    clock.now = 61
    with pytest.raises(ExpiredResult):
        reg.resolve(entry.id)
    with pytest.raises(UnknownResult):  # expired entries are dropped
        reg.resolve(entry.id)


def test_oldest_entries_are_evicted() -> None:
    reg = ResultRegistry(max_entries=2)
    first = reg.register("file", "1", target="1")
    reg.register("file", "2", target="2")
    reg.register("file", "3", target="3")
    assert len(reg) == 2
    with pytest.raises(UnknownResult):
        reg.resolve(first.id)


def test_public_view_never_contains_the_target() -> None:
    entry = ResultRegistry().register("file", "secret.pdf", target=r"C:\private\secret.pdf")
    public = entry.public().model_dump()
    assert "target" not in public
    assert r"C:\private\secret.pdf" not in str(public)

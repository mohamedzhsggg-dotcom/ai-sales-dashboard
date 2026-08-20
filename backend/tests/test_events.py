"""Domain event bus tests."""

from app.core.events import EventBus, bus


def test_publish_calls_subscriber():
    calls = []
    b = EventBus()
    b.subscribe("a.b", lambda e, p: calls.append((e, p)))
    b.publish("a.b", {"x": 1})
    assert calls == [("a.b", {"x": 1})]


def test_publish_payload_defaults_to_empty():
    b = EventBus()
    got = []
    b.subscribe("noop", lambda e, p: got.append(p))
    b.publish("noop")
    assert got == [{}]


def test_no_subscribers_is_noop():
    EventBus().publish("unsubscribed", {"x": 1})  # must not raise


def test_subscriber_error_isolated():
    b = EventBus()

    def bad(e, p):
        raise RuntimeError("boom")

    calls = []
    b.subscribe("x", bad)
    b.subscribe("x", lambda e, p: calls.append(e))
    b.publish("x")
    assert calls == ["x"]  # second subscriber still ran


def test_global_bus_is_singleton_style():
    assert bus is not None
import threading

import alive.main as main


def test_background_runner_delivers_result(monkeypatch):
    monkeypatch.setattr(main.GLib, "idle_add", lambda fn, *args: fn(*args) and False)
    done_event = threading.Event()
    results = []

    def done(value):
        results.append(value)
        done_event.set()

    main.GtkBackgroundRunner().run(lambda: 42, done)
    assert done_event.wait(2)
    assert results == [42]

from alive.apps import AppLauncher

def test_known_alias_launches_exact_argv():
    seen = []
    a = AppLauncher({"firefox": "firefox --new-window about:blank"}, seen.append)
    assert a.open("firefox") is True
    assert seen == [["firefox", "--new-window", "about:blank"]]

def test_unknown_alias_launches_nothing():
    seen = []
    a = AppLauncher({"code": "code"}, seen.append)
    assert a.open("rm -rf /") is False
    assert seen == []

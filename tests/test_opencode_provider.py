import json
import pytest

from alive.domain.contracts import ProviderError
from alive.infrastructure.providers.opencode import parse_opencode_output


def event(kind, **kw):
    return json.dumps({"type": kind, **kw})


def test_joins_text_parts_and_keeps_session_id():
    out = "\n".join([
        event("text", sessionID="ses_1", part={"type": "text", "messageID": "m1", "text": "Hola "}),
        event("text", sessionID="ses_1", part={"type": "text", "messageID": "m1", "text": "mundo"}),
    ])
    parsed = parse_opencode_output(out)
    assert parsed.text == "Hola mundo" and parsed.session_id == "ses_1"


def test_last_session_id_is_kept_for_logging():
    out = "\n".join([
        event("text", sessionID="ses_vieja", part={"type": "text", "messageID": "m1", "text": "uno"}),
        event("text", sessionID="ses_nueva", part={"type": "text", "messageID": "m1", "text": " uno"}),
    ])
    assert parse_opencode_output(out).session_id == "ses_nueva"


def test_keeps_only_the_last_message():
    out = "\n".join([
        event("text", sessionID="ses_1", part={"type": "text", "messageID": "m1", "text": "viejo"}),
        event("text", sessionID="ses_1", part={"type": "text", "messageID": "m2", "text": "nuevo"}),
    ])
    assert parse_opencode_output(out).text == "nuevo"


def test_free_limit_has_a_readable_error():
    out = event("error", error={"type": "provider.free-limit", "message": "Free usage limit reached"})
    with pytest.raises(ProviderError) as exc:
        parse_opencode_output(out)
    assert "límite gratuito" in str(exc.value)


def test_missing_agent_is_reported():
    out = event("error", error={"type": "unknown", "message": 'Agent not found: "alive"'})
    with pytest.raises(ProviderError) as exc:
        parse_opencode_output(out)
    assert "Falta el agente alive" in str(exc.value)


def test_empty_output_is_an_error():
    with pytest.raises(ProviderError) as exc:
        parse_opencode_output("")
    assert "no devolvió texto" in str(exc.value)


def test_unknown_events_and_reasoning_are_ignored():
    out = "\n".join([
        "esto no es json",
        event("step_start", sessionID="ses_1"),
        event("reasoning", sessionID="ses_1", part={"type": "reasoning", "text": "pienso"}),
        event("text", sessionID="ses_1", part={"type": "text", "messageID": "m1", "text": "ok"}),
    ])
    assert parse_opencode_output(out).text == "ok"

from alive.domain.orders import parse_orders

def test_extracts_only_allowed_orders():
    r = parse_orders("Hola\nESTADO=musica\nABRIR=firefox\nZONA=top\nESTADO=hablando\nFin")
    assert [(o.kind, o.value) for o in r.orders] == [("ESTADO", "musica"), ("ABRIR", "firefox")]
    assert r.ignored == ("ZONA=top", "ESTADO=hablando")

def test_orders_never_reach_bubble_text():
    r = parse_orders("Respuesta\nABRIR=code")
    assert r.clean_text == "Respuesta"
    assert "ABRIR" not in r.clean_text

def test_inline_fake_order_is_kept_as_text():
    r = parse_orders("Escribe ESTADO=musica en tu config")
    assert r.orders == ()
    assert r.clean_text == "Escribe ESTADO=musica en tu config"

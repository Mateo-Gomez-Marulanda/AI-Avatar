# Avatar de escritorio Alive — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un avatar flotante sobre KDE/Wayland que converse mediante un CLI de IA configurable, con animaciones decididas por un motor local y un intermediario, sin que el modelo gaste tokens en animación.

**Architecture:** Un surface GTK 3 + GtkLayerShell transparente dibuja el avatar y el globo. Un motor de animación puro posee estados y mouth; un intermediario traduce las respuestas del proveedor a estados, globo, voz y apertura de apps; un adaptador CLI configurable invoca opencode/Claude Code/otro con sesión reanudable. El modelo solo puede emitir `ESTADO=<grueso>` y `ABRIR=<alias>`.

**Tech Stack:** Python 3.14 (`tomllib`), GTK 3.24 + `GtkLayerShell 0.1` vía `gi`, pytest en `.venv` con `--system-site-packages`, D-Bus/`Gio`, `subprocess`, `ffmpeg`/PulseAudio para voz.

**Spec:** `/home/mateo/Documentos/Alive/plan-de-desarrollo.md`

## Global Constraints

- Sesión real: KDE Plasma sobre Wayland; no usar `xdotool`, `wmctrl`, `ydotool` ni `wtype`.
- La posición del surface se controla con anclas + márgenes de layer-shell, **nunca** con `window.move()`.
- Capa `OVERLAY`; `exclusive_zone = 0`; el avatar queda justo debajo del panel sin cubrir sus iconos ni desplazarlo.
- `keyboard_interactivity` desactivado por defecto; el campo de texto solo toma foco al abrirlo.
- Región de entrada activa = avatar/widgets; el resto del surface deja pasar clics.
- Contrato cerrado con el modelo: solo `ESTADO=<sentado|parado|musica>` y `ABRIR=<alias>`. Prohibido `ZONA=` y cualquier detalle de frames/timings/globo en el prompt.
- Proveedor de IA configurable por CLI; `session_mode=resume` por defecto cuando el CLI lo soporte. Sin modelos locales.
- v1: el avatar **abre** apps desde whitelist; no hace clic ni escribe dentro de ellas. Nunca `shell=True` con texto del modelo.
- Estados del motor: `sentado`, `parado`, `escuchando`, `pensando`, `hablando`, `musica`, `arrastrado`, `no_molestar`.
- Placeholders dibujados en código hasta que el usuario aporte arte; sustituibles sin tocar el motor.
- Python 3.14, GTK 3.24, `GtkLayerShell 0.1` — todos verificados en la máquina.
- Entorno de pruebas: `.venv` creado con `python3 -m venv --system-site-packages .venv`; pytest instalado dentro.

## Review Focus

- Texto de la IA con líneas que parecen órdenes → no deben filtrarse al globo; test en Task 2.
- `ABRIR=<alias>` inexistente → no se lanza nada, no rompe la respuesta; tests en Task 4 y Task 6.
- CLI con ANSI, banner, error o timeout → salida limpia y estado de vuelta a idle con mensaje visible; tests en Task 5 y Task 6.
- PTT sin audio o STT vacío → no se llama al modelo; tests en Task 6 y Task 7.
- Wayland no respeta la región de entrada o el anclaje tapa el panel → arrastre por asa y geometría correcta; checklist manual y test en Task 8.

---

## File Structure

```
alive/
  __init__.py
  config.py            Config, ProviderConfig, VoiceConfig, Zone, load_config
  orders.py            parser del contrato cerrado
  interfaces.py        Protocols: AiProvider, CommandRunner, AvatarViewLike, VoiceLike, BackgroundLike
  animation.py         AnimationEngine, Frame, STATES
  geometry.py          Rect, zone_rect, nearest_zone
  apps.py              AppLauncher con whitelist
  mediator.py          Mediator: turno, estados derivados, globo, voz, órdenes
  audio.py             VoiceService, rms_envelope
  providers/
    __init__.py
    base.py             AiReply, ProviderError
    cli.py              CliProvider, SubprocessRunner
  avatar_view.py       Gtk.Window + layer-shell + globo + arrastre
  input_panel.py       campo de texto + botón PTT
  main.py              wiring y GLib.MainLoop
config.toml.example
README.md
tests/
  test_config.py  test_orders.py  test_animation.py  test_geometry.py
  test_apps.py  test_cli_provider.py  test_mediator.py  test_audio.py
```

### Task 1: Scaffolding y configuración

**Files:**
- Create: `alive/__init__.py`, `alive/config.py`, `config.toml.example`, `tests/test_config.py`

**Interfaces:**
- Produces: `Zone(anchor: str, margin: int = 0, x: int = 0, y: int = 0, click_through: bool = False)`; `ProviderConfig(command: list[str], session_mode: str, session_flag: str = "", session_id_regex: str = "", timeout_s: float = 60.0, prompt_template: str = "")`; `VoiceConfig(stt_command: list[str] = field(default_factory=list), tts_command: list[str] = field(default_factory=list), play_command: list[str] = field(default_factory=list), capture_command: list[str] = field(default_factory=list), sample_rate: int = 16000, frame_samples: int = 1024, timeout_s: float = 30.0, enabled: bool = True)`; `Config(provider, apps: dict[str, str], zones: dict[str, Zone], voice, idle_state: str = "sentado", bubble_ms_per_char: int = 45, drag_snap_ms: int = 250)`; `ConfigError(ValueError)`; `load_config(path: str | Path) -> Config`.

- [ ] **Step 1: Crear entorno de pruebas y estructura**

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest
mkdir -p alive/providers tests
```

- [ ] **Step 2: Escribir los tests que fallan**

```python
# tests/test_config.py
from alive.config import ConfigError, load_config

def test_load_config_reads_provider_apps_and_zones(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["claude", "-p"]
session_mode = "resume"
prompt_template = "{history} | {text}"

[apps]
firefox = "firefox --new-window"

[zones.barra]
anchor = "top"
margin = 32

[voice]
stt_command = ["whisper"]
tts_command = ["piper"]
play_command = ["paplay", "--raw"]
capture_command = ["ffmpeg", "-t", "{duration}"]
''')
    c = load_config(p)
    assert c.provider.command == ["claude", "-p"]
    assert c.apps["firefox"] == "firefox --new-window"
    assert c.zones["barra"].anchor == "top" and c.zones["barra"].margin == 32
    assert c.idle_state == "sentado"

def test_load_config_rejects_bad_zone_anchor(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["x"]
[apps]
[zones.raro]
anchor = "techo"
[voice]
''')
    try:
        load_config(p)
    except ConfigError as e:
        assert "anchor" in str(e)
    else:
        raise AssertionError("debió fallar")
```

- [ ] **Step 3: Ejecutar para confirmar que fallan**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL, `ModuleNotFoundError: alive`

- [ ] **Step 4: Implementar `alive/config.py`**

Usar `tomllib` (stdlib). Validar: `provider.command` no vacío, `session_mode` en `{"resume","oneshot"}`, cada `Zone.anchor` en `{"top","left","right","bottom","floating"}`, `voice` presente. Aplicar defaults del bloque Interfaces. `Path` debe existir; si no, `ConfigError`. Un mensaje de error por campo inválido.

- [ ] **Step 5: Crear `config.toml.example`**

Copiar la configuración del test y añadir comentarios: cómo cambiar `command` a `opencode run`, `claude -p` u otro CLI; `session_flag = "--resume"` y `session_id_regex = "^SESSION=(.+)$"`; whitelist de apps; zonas `barra`, `izquierda`, `flotante`; comandos de voz de ejemplo.

- [ ] **Step 6: Ejecutar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS (2 tests)

```bash
git add .gitignore alive/__init__.py alive/config.py config.toml.example tests/test_config.py
git commit -m "feat: configuración cargada y validada"
```

Nota: crear `.gitignore` con `.venv/`, `__pycache__/`, `.pytest_cache/`.

---

### Task 2: Parser del contrato cerrado

**Files:**
- Create: `alive/orders.py`, `tests/test_orders.py`

**Interfaces:**
- Produces: `Order(kind: str, value: str)`; `ParseResult(clean_text: str, orders: tuple[Order, ...], ignored: tuple[str, ...])`; `parse_orders(text: str) -> ParseResult`; `ALLOWED_STATES = ("sentado", "parado", "musica")`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_orders.py
from alive.orders import parse_orders

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
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_orders.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.orders`

- [ ] **Step 3: Implementar `parse_orders`**

Solo líneas completas que coinciden exactamente con `ESTADO=(sentado|parado|musica)` o `ABRIR=[a-z0-9_-]+` (case-sensitive, sin espacios alrededor del `=`). Cualquier otra línea que empiece por `ESTADO=`, `ABRIR=` o `ZONA=` va a `ignored`. El resto se conserva en `clean_text` con `strip()` global.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_orders.py -q`
Expected: PASS (3 tests)

```bash
git add alive/orders.py tests/test_orders.py
git commit -m "feat: parser de órdenes cerrado"
```

---

### Task 3: Motor de animación puro

**Files:**
- Create: `alive/animation.py`, `tests/test_animation.py`

**Interfaces:**
- Consumes: nada externo; `Config.idle_state`, `Config.drag_snap_ms`, `Config.bubble_ms_per_char` (Task 1).
- Produces: `STATES` (los ocho de Global Constraints); `Frame(state: str, mouth: float, snap_progress: float)`; `AnimationEngine(idle_state="sentado", snap_ms=250, ms_per_char=45)` con `state`, `transition_to(state, now) -> None`, `speak(text, now) -> None`, `set_audio_level(level, now) -> None`, `begin_drag(now) -> None`, `end_drag(now) -> None`, `tick(now) -> Frame`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_animation.py
import pytest
from alive.animation import AnimationEngine, STATES

def test_unknown_state_is_rejected():
    with pytest.raises(ValueError):
        AnimationEngine().transition_to("buscando", 0.0)

def test_drag_returns_to_idle_after_snap():
    e = AnimationEngine()
    e.begin_drag(1.0)
    assert e.tick(1.0).state == "arrastrado"
    e.end_drag(2.0)
    assert e.tick(2.0).state == "arrastrado"
    assert e.tick(2.30).state == "sentado"
    assert 0.0 <= e.tick(2.10).snap_progress <= 1.0

def test_speaking_mouth_is_deterministic_and_clamped():
    e = AnimationEngine()
    e.speak("hola", 0.0)
    assert e.tick(0.05).state == "hablando"
    assert 0.0 <= e.tick(0.05).mouth <= 1.0
    e.set_audio_level(5.0, 1.0)
    assert e.tick(1.0).mouth <= 1.0
    assert all(s in STATES for s in ("pensando", "no_molestar", "musica"))
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_animation.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.animation`

- [ ] **Step 3: Implementar `alive/animation.py`**

`tiempo` es `float` en segundos inyectado por el llamador. `transition_to` valida contra `STATES`. `speak` guarda `speaking_until = now + len(text)*ms_per_char/1000`. `set_audio_level` guarda nivel clampeado 0..1 y `audio_at=now`; expira 0.12 s después. Al expirar `speaking_until`, el estado vuelve a `idle_state`. `begin_drag` marca arrastre; `end_drag` guarda `return_at = now + snap_ms/1000` y `snap_progress` crece de 0 a 1 hasta ese instante; al cumplirse, vuelve a `idle_state`. En `tick`, boca = nivel de audio si fresco, si no alternancia determinista `0.7 if int(now*10)%2==0 else 0.1` mientras `hablando`, si no 0.0.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_animation.py -q`
Expected: PASS (3 tests)

```bash
git add alive/animation.py tests/test_animation.py
git commit -m "feat: motor de estados y boca sin IA"
```

---

### Task 4: Apertura de apps desde whitelist

**Files:**
- Create: `alive/apps.py`, `tests/test_apps.py`

**Interfaces:**
- Consumes: `Config.apps: dict[str, str]`.
- Produces: `AppLauncher(whitelist: dict[str, str], spawn: Callable[[list[str]], None])` con `open(alias: str) -> bool`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_apps.py
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
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_apps.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.apps`

- [ ] **Step 3: Implementar `AppLauncher`**

`shlex.split` del valor de la whitelist; `spawn(argv)`; `False` si alias ausente o comando vacío. Sin `shell=True`, sin interpolación.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_apps.py -q`
Expected: PASS (2 tests)

```bash
git add alive/apps.py tests/test_apps.py
git commit -m "feat: whitelist de aplicaciones"
```

---

### Task 5: Adaptador de IA por CLI

**Files:**
- Create: `alive/interfaces.py`, `alive/providers/__init__.py`, `alive/providers/base.py`, `alive/providers/cli.py`, `tests/test_cli_provider.py`

**Interfaces:**
- Consumes: `ProviderConfig` (Task 1).
- Produces: en `interfaces.py`, `AiProvider` con `ask(prompt: str, history: tuple[str, ...]) -> AiReply`; `CommandRunner` con `run(argv: list[str], stdin: bytes, timeout_s: float) -> str`; en `base.py`, `AiReply(text: str)`, `ProviderError(RuntimeError)`; en `cli.py`, `CliProvider(config: ProviderConfig, runner: CommandRunner)` y `SubprocessRunner()`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_cli_provider.py
from alive.config import ProviderConfig
from alive.providers.cli import CliProvider, SubprocessRunner

def test_strips_ansi_from_output():
    out = "\x1b[31mHola\x1b[0m mundo"
    p = CliProvider(ProviderConfig(command=["x"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "Hola mundo"

def test_resume_reuses_session_id():
    calls = []
    def runner(argv, stdin, timeout_s):
        calls.append(argv)
        return "primera\nSESSION=abc123\n" if len(calls) == 1 else "segunda\nSESSION=abc123\n"
    cfg = ProviderConfig(command=["cli"], session_mode="resume", session_flag="--resume",
                         session_id_regex=r"^SESSION=(.+)$")
    p = CliProvider(cfg, runner)
    assert p.ask("uno", ()).text == "primera"
    p.ask("dos", ("uno",))
    assert "--resume" in calls[1] and "abc123" in calls[1]
    assert "--resume" not in calls[0]

def test_oneshot_never_passes_session_flag():
    calls = []
    p = CliProvider(ProviderConfig(command=["cli"], session_mode="oneshot", session_flag="--resume"),
                    lambda argv, stdin, timeout_s: (calls.append(argv), "ok")[1])
    p.ask("uno", ()); p.ask("dos", ("uno",))
    assert all("--resume" not in c for c in calls)

def test_runner_reports_timeout():
    import pytest
    from alive.providers.base import ProviderError
    with pytest.raises(ProviderError):
        SubprocessRunner().run(["python3", "-c", "import time; time.sleep(1)"], b"", 0.01)
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_cli_provider.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.interfaces`

- [ ] **Step 3: Implementar proveedores**

`interfaces.py` define los Protocols con los tipos de arriba e importa `AiReply` de `alive.providers.base` (que no importa `interfaces`, para evitar ciclos). `CliProvider.ask`: arma `argv = config.command + ([config.session_flag, session_id] si resume y hay id)`, codifica el prompt (plantilla con `{history}` y `{text}`; si no hay plantilla, `history` con saltos de línea + texto) a bytes, llama `runner`, quita ANSI con `re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)`, busca `session_id_regex` con `re.MULTILINE` solo si la expresión no está vacía, guarda el id, elimina del texto visible las líneas que coinciden con esa expresión y devuelve `AiReply(text=limpio)`. `SubprocessRunner.run`: `subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout_s)`, devuelve `stdout.decode(errors="replace")`; `TimeoutExpired`/`CalledProcessError`/`OSError` → `ProviderError` con mensaje corto.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_cli_provider.py -q`
Expected: PASS (4 tests)

```bash
git add alive/interfaces.py alive/providers tests/test_cli_provider.py
git commit -m "feat: adaptador CLI configurable con sesión reanudable"
```

---

### Task 6: Intermediario

**Files:**
- Create: `alive/mediator.py`, `tests/test_mediator.py`

**Interfaces:**
- Consumes: `AnimationEngine` (Task 3), `AppLauncher` (Task 4), `AiProvider`/`AiReply` (Task 5), `parse_orders`/`Order` (Task 2), `Config` (Task 1).
- Produces: en `interfaces.py` (modificar), `AvatarViewLike` con `show_bubble(text: str, ms_per_char: int) -> None`, `hide_bubble() -> None`, `render(frame: Frame) -> None`, `set_click_through(enabled: bool) -> None`, `snap_to(zone_name: str) -> None`; `VoiceLike` con `transcribe(audio: bytes) -> str`, `speak(text: str, on_level: Callable[[float, float], None]) -> None`, `record(seconds: float) -> bytes`; `BackgroundLike.run(work: Callable[[], T], done: Callable[[T], None]) -> None`. `Mediator(engine, view, ai, voice, launcher, config, clock, background)` con `submit_text(text)`, `ptt_start()`, `ptt_end(held_seconds)`, `toggle_no_molestar()`, `on_drag_start()`, `on_drag_end(zone_name)`, `apply_order(order)`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_mediator.py
from alive.mediator import Mediator
from alive.orders import Order
from alive.config import Config, ProviderConfig, VoiceConfig

class Inline:
    def run(self, work, done): done(work())

def make(**kw):
    cfg = Config(provider=ProviderConfig(command=["x"], session_mode="oneshot"),
                 apps={"firefox": "firefox"}, zones={}, voice=VoiceConfig([], [], [], []))
    base = dict(engine=kw.get("engine"), view=kw.get("view"), ai=kw.get("ai"),
                voice=kw.get("voice"), launcher=kw.get("launcher"),
                config=cfg, clock=lambda: 0.0, background=Inline())
    return Mediator(**base)

def test_answer_shows_bubble_and_speaks():
    from alive.animation import AnimationEngine
    class V:
        def __init__(self): self.bubble=None
        def show_bubble(self, text, ms): self.bubble=text
        def hide_bubble(self): pass
        def render(self, frame): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class A:
        def ask(self, prompt, history): from alive.providers.base import AiReply; return AiReply("Hola\nABRIR=firefox")
    class Voice:
        def record(self, s): return b""
        def transcribe(self, a): return ""
        def speak(self, text, on_level): self.spoken=text
    class L:
        def __init__(self): self.opened=[]
        def open(self, alias): self.opened.append(alias); return True
    e, v, voice, l = AnimationEngine(), V(), Voice(), L()
    m = make(engine=e, view=v, ai=A(), voice=voice, launcher=l)
    m.submit_text("¿qué tal?")
    assert v.bubble == "Hola" and voice.spoken == "Hola" and l.opened == ["firefox"]
    assert e.state == "hablando"

def test_empty_ptt_does_not_call_ai():
    from alive.animation import AnimationEngine
    class Voice:
        def record(self, s): return b"xyz"
        def transcribe(self, a): return "   "
        def speak(self, text, on_level): raise AssertionError("no debe hablar")
    class AI:
        def ask(self, p, h): raise AssertionError("no debe llamar al modelo")
    e = AnimationEngine()
    m = make(engine=e, view=object(), ai=AI(), voice=Voice(), launcher=object())
    m.ptt_start(); m.ptt_end(0.5)
    assert e.state == "sentado"

def test_provider_error_returns_to_idle_with_message():
    from alive.animation import AnimationEngine
    from alive.providers.base import ProviderError
    class V:
        def show_bubble(self, text, ms): self.bubble=text
        def hide_bubble(self): pass
        def render(self, f): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class AI:
        def ask(self, p, h): raise ProviderError("timeout")
    class Voice:
        def record(self,s): return b""
        def transcribe(self,a): return ""
        def speak(self,t,on_level): pass
    e, v = AnimationEngine(), V()
    m = make(engine=e, view=v, ai=AI(), voice=Voice(), launcher=object())
    m.submit_text("pregunta")
    assert e.state == "sentado" and "No pude responder" in v.bubble

def test_unknown_app_order_is_ignored():
    from alive.animation import AnimationEngine
    e = AnimationEngine(); m = make(engine=e, view=object(), ai=object(), voice=object(),
                                    launcher=object())
    assert m.apply_order(Order("ABRIR", "inexistente")) is False
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_mediator.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.mediator`

- [ ] **Step 3: Implementar `Mediator`**

Añadir los Protocols a `alive/interfaces.py`. `submit_text`: ignorar texto vacío; `engine.transition_to("escuchando", clock())`; `background.run(lambda: ai.ask(prompt, history), self._finish)`. `_finish(reply)`: `parse_orders(reply.text)`; aplicar órdenes (`ESTADO` → `transition_to`, `ABRIR` → `launcher.open`); `engine.speak(clean_text or "ok", clock())`; `view.show_bubble(...)`; `voice.speak(clean_text, on_level=lambda lvl, t: engine.set_audio_level(lvl, t))`. `ProviderError` → `view.show_bubble("No pude responder", ...)` y `transition_to(idle_state)`. `ptt_start` → `escuchando`; `ptt_end` → `background.run(lambda: voice.transcribe(voice.record(held_seconds)), lambda text: self.submit_text(text) if text.strip() else engine.transition_to(idle))`. `apply_order` devuelve `bool`; `ABRIR` con alias no white-listado devuelve False; `ESTADO` fuera de `ALLOWED_STATES` devuelve False. `toggle_no_molestar` alterna `no_molestar`/idle y `view.set_click_through`. Drag delega en `engine.begin_drag/end_drag` y `view.snap_to`.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_mediator.py -q`
Expected: PASS (4 tests)

```bash
git add alive/interfaces.py alive/mediator.py tests/test_mediator.py
git commit -m "feat: intermediario con estados derivados y globo"
```

---

### Task 7: Voz configurables y sincronización de boca

**Files:**
- Create: `alive/audio.py`, `tests/test_audio.py`

**Interfaces:**
- Consumes: `VoiceConfig` (Task 1), `CommandRunner` (Task 5).
- Produces: `rms_envelope(pcm: bytes, sample_width: int = 2, frame_samples: int = 1024) -> list[float]`; `VoiceService(config: VoiceConfig, runner: CommandRunner, sleep: Callable[[float], None] = time.sleep)` con `record(seconds: float) -> bytes`, `transcribe(audio: bytes) -> str`, `speak(text: str, on_level: Callable[[float, float], None]) -> None`.

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_audio.py
import struct
from alive.audio import VoiceService, rms_envelope

def test_rms_envelope_silence_and_tone():
    assert rms_envelope(b"\x00" * 2048, frame_samples=1024) == [0.0, 0.0]
    loud = struct.pack("<h", 16000) * 1024 + b"\x00" * 1024
    vals = rms_envelope(loud, frame_samples=1024)
    assert vals[0] > 0.3 and vals[1] == 0.0

def test_record_replaces_duration_placeholder():
    calls = []
    cfg = type("C", (), {"capture_command": ["ffmpeg", "-t", "{duration}", "-i", "x"],
                         "sample_rate": 16000, "frame_samples": 1024})()
    v = VoiceService(cfg, lambda argv, stdin, timeout_s: (calls.append(argv), b"pcm")[1], lambda s: None)
    assert v.record(2.5) == b"pcm" and calls[0][2] == "2.5"

def test_speak_feeds_levels_in_order():
    levels, sleeps = [], []
    cfg = type("C", (), {"tts_command": ["tts"], "play_command": ["paplay"],
                         "sample_rate": 16000, "frame_samples": 1024, "timeout_s": 5.0})()
    runner = lambda argv, stdin, timeout_s: b"\x00" * 2048 if argv[0] == "tts" else ""
    v = VoiceService(cfg, runner, lambda s: sleeps.append(s))
    v.speak("hola", lambda level, t: levels.append(level))
    assert levels == [0.0, 0.0]
    assert sleeps == [0.064, 0.064]
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_audio.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.audio`

- [ ] **Step 3: Implementar `alive/audio.py`**

`rms_envelope`: agrupar en `frame_samples`, normalizar RMS entre 0 y 1 dividiendo por 32768. `record`: reemplazar `{duration}` en cada argumento por `str(seconds)`, ejecutar `capture_command` con `timeout=seconds+2`, devolver bytes. `transcribe`: `runner(stt_command, audio, timeout)`, devolver texto limpio. `speak`: ejecutar `tts_command` con texto en bytes → PCM; ejecutar `play_command` con ese PCM; por cada frame de la envolvente llamar `on_level(level, time.monotonic())` y `sleep(frame_samples/sample_rate)`. Usar `cfg.timeout_s` en las dos llamadas al runner.

- [ ] **Step 4: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_audio.py -q`
Expected: PASS (3 tests)

```bash
git add alive/audio.py tests/test_audio.py
git commit -m "feat: voz configurable y boca por envolvente"
```

---

### Task 8: Vista GTK, layer-shell, zonas y arrastre

**Files:**
- Create: `alive/geometry.py`, `alive/avatar_view.py`, `tests/test_geometry.py`

**Interfaces:**
- Consumes: `Zone`/`Config` (Task 1), `Frame` (Task 3), `AvatarViewLike` (Task 6).
- Produces: `Rect(x: int, y: int, width: int, height: int)`; `zone_rect(monitor: Rect, zone: Zone, size: tuple[int, int]) -> Rect`; `nearest_zone(monitor: Rect, pointer: tuple[int, int], zones: dict[str, Zone], size: tuple[int, int]) -> str`; `AvatarView(config: Config, monitor: Rect)` con los métodos de `AvatarViewLike` y `set_callbacks(on_drag_start, on_drag_end, on_activate_input)`.

- [ ] **Step 1: Tests que fallan (geometría pura)**

```python
# tests/test_geometry.py
from alive.config import Zone
from alive.geometry import Rect, nearest_zone, zone_rect

MON = Rect(0, 0, 1920, 1080)
SZ = (200, 300)

def test_top_zone_sits_below_panel_without_covering_it():
    r = zone_rect(MON, Zone("top", margin=32), SZ)
    assert (r.x, r.y, r.width, r.height) == (860, 32, 200, 300)

def test_side_zones_and_floating():
    assert zone_rect(MON, Zone("left", margin=10), SZ).x == 10
    assert zone_rect(MON, Zone("right", margin=10), SZ).x == 1710
    assert zone_rect(MON, Zone("floating", x=100, y=200), SZ).y == 200

def test_nearest_zone_picks_closest_edge():
    zones = {"barra": Zone("top", 32), "izq": Zone("left", 10), "der": Zone("right", 10)}
    assert nearest_zone(MON, (5, 500), zones, SZ) == "izq"
    assert nearest_zone(MON, (1910, 500), zones, SZ) == "der"
```

- [ ] **Step 2: Verificar fallo**

Run: `.venv/bin/python -m pytest tests/test_geometry.py -q`
Expected: FAIL, `ModuleNotFoundError: alive.geometry`

- [ ] **Step 3: Implementar `geometry.py`**

`zone_rect`: `top` → `x=(monitor.width-size.w)//2`, `y=zone.margin`; `left`/`right` → `y=(monitor.height-size.h)//2`, `x=margin` o `monitor.width-size.w-margin`; `bottom` → `y=monitor.height-size.h-margin`; `floating` → `x=zone.x, y=zone.y`. `nearest_zone`: distancia desde el puntero al centro del rect de cada zona; devuelve la menor; si `zones` vacío, `"flotante"`.

- [ ] **Step 4: Implementar `avatar_view.py`**

Antes de importar `gi.repository`, ejecutar `gi.require_version("Gtk", "3.0")` y `gi.require_version("GtkLayerShell", "0.1")`. `Gtk.Window` con `app_paintable=True`, fondo transparente por CSS; `GtkLayerShell.init_for_window`, `set_layer(GtkLayerShell.Layer.OVERLAY)`, `set_anchor` según la zona actual, `set_margin(..., zone.margin)`, `set_exclusive_zone(0)`, `set_keyboard_interactivity(False)`. Dibujar placeholder del avatar con `Gtk.DrawingArea` (formas por estado) y globo con `Gtk.Label` en `Gtk.Overlay`. Región de entrada: `input_shape_combine_region` con la silueta del avatar y el globo; `set_click_through(True)` aplica región vacía. Arrastre: `button-press-event`/`motion-notify-event`/`button-release-event` actualizan márgenes con `zone_rect`/`nearest_zone` (nunca `window.move()`); al soltar llama `on_drag_end(nombre_zona)`. `render(frame)` aplica `frame.mouth` al dibujo e interpola posición con `frame.snap_progress`. `show_bubble(text, ms)` muestra el texto y programa ocultarlo tras `len(text)*ms`.

- [ ] **Step 5: Verificación manual en Wayland (F0–F2)**

Run: `PYTHONPATH=. .venv/bin/python -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; from alive.avatar_view import AvatarView; from alive.geometry import Rect; from alive.config import load_config; v=AvatarView(load_config('config.toml.example'), Rect(0,0,1920,1080)); v.show_all(); Gtk.main()"`

Esperado: el avatar aparece transparente sobre las ventanas, se puede arrastrar, al soltar se ancla a barra/costado, no desplaza el panel de Plasma y los clics en el área vacía pasan a la ventana de debajo. Si Wayland ignora la región de entrada, añadir un asa visible de 24×24 px como única zona activa y repetir la comprobación.

- [ ] **Step 6: Pasar tests y commit**

Run: `.venv/bin/python -m pytest tests/test_geometry.py -q`
Expected: PASS (3 tests)

```bash
git add alive/geometry.py alive/avatar_view.py tests/test_geometry.py
git commit -m "feat: overlay layer-shell, zonas y arrastre"
```

---

### Task 9: Panel de texto, PTT, wiring y documentación

**Files:**
- Create: `alive/input_panel.py`, `alive/main.py`, `README.md`
- Modify: `config.toml.example`

**Interfaces:**
- Consumes: todos los componentes anteriores; `Mediator` (Task 6), `AvatarView` (Task 8), `CliProvider`/`SubprocessRunner` (Task 5), `VoiceService` (Task 7), `AppLauncher` (Task 4), `CommandRunner` (Task 5).
- Produces: `InputPanel(on_text_submit: Callable[[str], None], on_ptt_hold: Callable[[float], None])` con `show()`; `GtkBackgroundRunner` en `main.py` implementando `BackgroundLike`; entry point `python -m alive.main --config config.toml`.

- [ ] **Step 1: Implementar `input_panel.py`**

`Gtk.Window` pequeña, no always-on-top, con `Gtk.Entry` + botón «Enviar» + botón «Micrófono» (pulsación mantenida). `show()` solo la ventana del panel; `hide()` la oculta; `present()` pide foco. En `button-press-event` del micrófono guardar `time.monotonic()`; en `release-event` llamar `on_ptt_hold(segundos)`. `Enter` en el entry llama `on_text_submit` con el texto y lo limpia.

- [ ] **Step 2: Implementar `main.py`**

`argparse` con `--config` (por defecto `config.toml`). Cargar config; `monitor = Rect(g.x, g.y, g.width, g.height)` obtenido con `g = Gdk.Display.get_default().get_monitor(0).get_geometry()`. Construir `runner=SubprocessRunner()`, `ai=CliProvider(cfg.provider, runner)`, `voice=VoiceService(cfg.voice, runner)`, `launcher=AppLauncher(cfg.apps, lambda argv: subprocess.Popen(argv))`, `engine=AnimationEngine(cfg.idle_state, cfg.drag_snap_ms, cfg.bubble_ms_per_char)`, `view=AvatarView(cfg, monitor)`, `panel=InputPanel(...)`. `GtkBackgroundRunner.run` ejecuta `work` en `threading.Thread(daemon=True)` y llama `GLib.idle_add(done, resultado)`. Conectar `on_drag_start`/`on_drag_end` de la vista y `on_text_submit`/`on_ptt_hold` del panel al mediador; `on_activate_input` de la vista llama `panel.show()` y `panel.present()`. Registrar un `GLib.timeout_add(33, ...)` que en cada disparo llama `view.render(engine.tick(time.monotonic()))` y devuelve `True`; arrancar `Gtk.main()`. Si `voice.enabled` es False, no crear atajos de voz y ocultar el botón.

- [ ] **Step 3: Actualizar `config.toml.example` y `README.md`**

Documentar: creación de `.venv`, instalación, ejecución, cambio de proveedor CLI (`opencode run`, `claude -p`, otro), `session_mode`, `session_flag`/`session_id_regex`, whitelist de apps, zonas y «no molestar», y cómo sustituir el placeholder por arte propio. Incluir checklist de aceptación manual: pregunta → globo + boca; arrastre → anclaje; micrófono → transcripción y respuesta; `ABRIR=firefox` → app abierta; clicks en zona vacía → pasan a la ventana de debajo.

- [ ] **Step 4: Verificación completa**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (todos los tests; al menos 18)

Run: `PYTHONPATH=. .venv/bin/python -m alive.main --config config.toml.example`
Expected: avatar visible; pregunta por texto → respuesta en globo y boca animada; arrastre → snap; PTT → transcripción y respuesta; orden `ABRIR=<alias>` abre la app.

- [ ] **Step 5: Commit final**

```bash
git add alive/input_panel.py alive/main.py README.md config.toml.example
git commit -m "feat: interfaz de texto/PTT y arranque del avatar"
```

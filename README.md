# Alive — avatar 2D para Linux/KDE

Un avatar flotante sobre el escritorio que conversa con un modelo por CLI. El modelo
**no decide animaciones**: solo puede pedir `ESTADO=sentado|parado|musica` y
`ABRIR=<alias>`. Todo lo demás (escuchar, pensar, hablar, arrastrar, boca, snap) lo
decide el motor local.

## Requisitos

- KDE Plasma con Wayland (probado en Plasma 6 / Wayland).
- GTK 3 + GtkLayerShell (`GtkLayerShell-0.1.typelib`), PyGObject y pycairo.
- Python 3.11+ (`tomllib`).
- Cualquier CLI de IA que lea por stdin y escriba por stdout.

En Arch, por ejemplo: `pacman -S gtk3 gtk-layer-shell python-gobject python-cairo`.

## Instalación y arranque

```bash
cp config.toml.example config.toml
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest        # solo para desarrollar
PYTHONPATH=. .venv/bin/python -m alive.main --config config.toml
```

El avatar aparece **debajo** del panel superior: no tapa los iconos ni desplaza la
barra. Para hablar, haz clic sobre el avatar (se abre el panel) o pulsa el botón
«Micrófono» y suéltalo después de hablar. «No molestar» activa el estado y deja
pasar los clics; vuelve a pulsarlo para restaurar la interacción.

## Configuración

### Proveedor de IA

`[provider] command` es la única pieza ligada al proveedor:

| Proveedor | `command` |
| --- | --- |
| Claude Code | `["claude", "-p"]` |
| OpenCode | `["opencode", "run"]` |
| OpenAI Codex | `["codex", "exec"]` |

`session_mode = "resume"` reutiliza la sesión del CLI. Para los CLI que aceptan un
id, `session_flag` es el argumento (p. ej. `--resume`) y `session_id_regex` extrae
el id de la salida (`^SESSION=(.+)$`). Si el CLI no expone id, deja
`session_id_regex = ""`: se envía el historial en cada llamada. Con
`session_mode = "oneshot"` nunca se pasa `session_flag`.

`prompt_template` usa `{history}` y `{text}`. El contrato de órdenes se explica en
el propio `config.toml.example`: el modelo solo puede emitir `ESTADO` y `ABRIR`.

### Apps

`[apps]` es la whitelist: `alias = "comando con argumentos"`. El modelo solo puede
pedir `ABRIR=alias` si el alias existe ahí; un alias desconocido se ignora. El
comando se divide con `shlex`, no se pasa a un shell.

### Zonas

Cada `[zones.nombre]` define `anchor` (`top`, `left`, `right`, `bottom`,
`floating`), `margin` y, solo para `floating`, `x`/`y`. Al soltar el avatar tras
arrastrarlo, se ancla a la zona cuyo centro queda más cerca del cursor. El anclaje
superior usa `margin` como altura del panel (p. ej. 32 px).

### Voz

`[voice].enabled = false` oculta el micrófono. `capture_command` graba PCM con
`{duration}` como marcador de segundos; `stt_command` recibe el audio por stdin;
`tts_command` recibe el texto y devuelve PCM crudo; `play_command` reproduce ese
PCM. `sample_rate` y `frame_samples` deben coincidir con el TTS para que la boca
sincronice. La boca usa la envolvente RMS del PCM; si no hay TTS, se mueve de
forma determinista mientras dura el globo.

## Arte propio

El avatar actual es un placeholder dibujado en `alive/avatar_view.py`, método
`_draw`, con `_STATE_COLORS` por estado. Sustituye ese método por tu sprite o SVG
manteniendo la interfaz: `render(frame)` entrega `frame.state`, `frame.mouth`
(0–1) y `frame.snap_progress` (0–1). El tamaño del sprite se cambia en `_SIZE` de
ese mismo archivo. La silueta que acepta clics se ajusta en `_BODY`/`_HEAD`.

## Comprobación manual

1. Pregunta por texto → aparece el globo y la boca se anima.
2. Arrastre → al soltar se ancla a barra o costado; el panel de Plasma no se mueve.
3. Micrófono mantenido → transcripción y respuesta.
4. Respuesta con `ABRIR=firefox` → se abre Firefox.
5. Clic en el área vacía alrededor del avatar → pasa a la ventana de debajo.
6. «No molestar» → el avatar deja de recibir clics y vuelve al pulsar de nuevo.

## Tests

```bash
.venv/bin/python -m pytest -q
```

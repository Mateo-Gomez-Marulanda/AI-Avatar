# Alive — avatar 2D para Linux/KDE

Alive es un avatar flotante dibujado con GTK3 + GtkLayerShell que conversa con un
CLI de IA y muestra las respuestas en un globo. Vive **debajo** del panel superior:
no tapa los iconos ni desplaza la barra.

La regla central es la separación de decisiones: **la IA nunca decide animaciones**.
Solo puede emitir dos órdenes, `ESTADO=sentado|parado|musica` y `ABRIR=<alias>`.
Escuchar, pensar, hablar, mover la boca, arrastrar y hacer snap los decide el motor
local (`alive/domain/animation.py`). Cualquier otra línea (`ZONA=…`,
`ESTADO=hablando`, etc.) se ignora.

## Qué hace y qué no hace

**Hace**

- Overlay transparente anclado a zonas de la pantalla (barra, costados o flotante).
- Panel de texto, micrófono de pulsación mantenida (PTT) y botón «No molestar».
- Globos de texto, boca sincronizada con la envolvente RMS del audio.
- Arranque de aplicaciones permitidas por una whitelist.
- Cierre limpio con el botón «Salir» o `Ctrl+Q`.

**No hace**

- No incluye ni reemplaza a Veadotube: el renderer es propio.
- No trae modelos locales: delega en cualquier CLI configurable.
- No instala motores de voz: STT/TTS dependen de binarios del sistema.
- No registra atajos globales del sistema.
- No mueve el panel de texto al layer-shell: es una ventana GTK normal.

## Requisitos

- KDE Plasma con Wayland (probado en Plasma 6 / Wayland).
- GTK 3, GtkLayerShell (`GtkLayerShell-0.1.typelib`), PyGObject y pycairo.
- Python 3.11+ (`tomllib`).
- Un CLI de IA que lea por stdin y escriba por stdout.
- Para voz: `ffmpeg` (captura), `whisper-cli` (STT), `piper` (TTS) y `paplay`
  (reproducción). Si faltan, el avatar avisa y oculta el micrófono.

En Arch, por ejemplo:

```bash
pacman -S gtk3 gtk-layer-shell python-gobject python-cairo
```

## Instalación y arranque

```bash
cp config.toml.example config.toml
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest        # solo para desarrollar
PYTHONPATH=. .venv/bin/python -m alive.main --config config.toml
```

`--config` es opcional y por defecto vale `config.toml`. El archivo de ejemplo
trae `voice.enabled = true` con rutas de modelos que probablemente no tengas:
ajústalo a tus binarios o pon `enabled = false` para usar solo texto.

## Uso e interacción

- **Clic sobre el avatar** abre el panel de texto. Se tolera un temblor de hasta
  10 px entre pulsar y soltar; un movimiento mayor se considera arrastre.
- **Panel**: escribe y pulsa Enter o «Enviar». «Micrófono» funciona como PTT:
  mantén pulsado mientras hablas y suelta para transcribir. «No molestar» pone
  el avatar en ese estado y deja pasar los clics; vuelve a pulsarlo para
  restaurarlo. «Salir» cierra el programa.
- **Arrastre**: pulsa, mueve y suelta. El avatar sigue al cursor aunque este
  salga de la ventana y luego se desplaza con una animación de snap (~250 ms)
  hasta la zona cuyo centro queda más cerca. Empezar otro arrastre cancela el
  snap anterior; un clic no lo cancela.
- **`Ctrl+Q`** cierra el programa cuando el panel tiene el foco.
- **Voz**: la cadena es captura → STT → IA → TTS → PCM → boca. Si falta algún
  comando se muestra «Voz no disponible: faltan herramientas» y el micrófono
  desaparece. Si la transcripción falla aparece «No pude escuchar»; si falla el
  TTS, la respuesta escrita sigue visible.

## Cómo fluye la información

```
Texto / PTT
    │
    ▼
InputPanel (ui) ──callbacks──▶ Mediator (application)
                                  ├─▶ CliProvider (infrastructure) ──▶ CLI de IA
                                  ├─▶ parse_orders (domain) ──▶ ESTADO / ABRIR
                                  │                              └─▶ AppLauncher
                                  ├─▶ AnimationEngine (domain) ──▶ Frame
                                  │        ▲
                                  │        └── VoiceService ──▶ nivel de audio
                                  ▼
                          AvatarView.render (ui) ──▶ layer-shell + cairo
```

`AnimationEngine.tick()` produce un `Frame(state, mouth, snap_progress)`.
`main.py` lo llama cada 33 ms con `GLib.timeout_add` y entrega el resultado a la
vista. Las llamadas al CLI y la captura/transcripción de voz corren en hilos de
fondo (`GtkBackgroundRunner`) y vuelven al hilo GTK con `GLib.idle_add`, para no
bloquear la interfaz. La síntesis de voz (`speak`) se ejecuta en el hilo GTK.

## Estructura de carpetas

| Ruta | Contribución al desarrollo |
| --- | --- |
| `alive/domain/` | Reglas puras del negocio: `config.py` (TOML y validación), `orders.py` (contrato cerrado), `animation.py` (estados, boca y snap), `geometry.py` (zonas y rectángulos), `contracts.py` (tipos y protocolos). Python puro: ni GTK ni `subprocess`. |
| `alive/application/` | Casos de uso: `mediator.py` interpreta respuestas y coordina estado, globo, voz y apps; `audio.py` implementa captura/STT/TTS y la detección de binarios ausentes; `apps.py` aplica la whitelist. No contiene widgets. |
| `alive/infrastructure/` | Adaptadores al mundo exterior: `providers/cli.py` habla con el CLI y limpia su salida; `background.py` ejecuta trabajo en hilos y devuelve resultados con GLib. |
| `alive/ui/` | Todo lo visible: `avatar_view.py` dibuja el avatar con cairo, gestiona eventos, márgenes layer-shell, globo y snap; `input_panel.py` es la ventana de texto, PTT, «No molestar» y «Salir». |
| `alive/main.py` | Raíz de composición: carga la configuración, obtiene el monitor, construye e inyecta las dependencias, conecta callbacks, registra el tick y arranca `Gtk.main()`. Es el único lugar que importa todas las capas y GTK para el bootstrap. |
| `alive/providers/` | Directorio vacío heredado de la estructura anterior. Los proveedores reales viven en `alive/infrastructure/providers/`. |
| `tests/` | Suite plana de pytest: un archivo por módulo, más `test_structure.py` (comprueba que los imports de cada capa siguen disponibles) y `fixtures/fake_config.toml` (config aislada, sin rutas de `/tmp`). |
| `docs/` | `estructura-proyecto.md` (diseño por capas), `interaccion-y-salida.md` (especificación de clic, salida y voz) y `superpowers/plans/` (planes de ejecución: la carpeta está ignorada para archivos nuevos, aunque algunos planes antiguos siguen versionados). |
| Raíz del repo | `config.toml.example` (plantilla comentada), `plan-de-desarrollo.md` (diseño original y fuente de verdad) y este README. |
| Ignorados | `.venv/`, `__pycache__/`, `.pytest_cache/`, `.superpowers/` y `superpowers/` son entornos, cachés y scratch de desarrollo; no forman parte del código. |

Las dependencias apuntan en una sola dirección: `ui`, `application` e
`infrastructure` pueden importar `domain`; `domain` no importa nada de esas
capas; `main.py` importa todas para cablearlas. `test_structure.py` importa los
módulos de cada capa para detectar que la reorganización sigue intacta.

## Configuración

- **`[provider]`**: `command` es la única pieza ligada al proveedor. El ejemplo
  usa OpenCode: `command = ["opencode", "run"]` con
  `session_mode = "oneshot"`, que envía el historial en cada llamada sin depender
  de ids de sesión. Otras opciones:

  | Proveedor | `command` |
  | --- | --- |
  | Claude Code | `["claude", "-p"]` |
  | OpenCode | `["opencode", "run"]` |
  | OpenAI Codex | `["codex", "exec"]` |

  `session_mode = "resume"` reutiliza la sesión del CLI; con `session_flag` y
  `session_id_regex` se extrae el id de la salida. `prompt_template` usa
  `{history}` y `{text}`.
- **`[apps]`**: whitelist `alias = "comando con argumentos"`. El modelo solo
  puede pedir `ABRIR=alias` si el alias existe; el comando se divide con
  `shlex`, nunca pasa por un shell.
- **`[zones.nombre]`**: `anchor` (`top`, `left`, `right`, `bottom`,
  `floating`), `margin` y, solo para `floating`, `x`/`y`. Al soltar, se ancla a
  la zona más cercana al cursor. `margin` del anclaje superior es la altura del
  panel (p. ej. 32 px).
- **`[voice]`**: `enabled`, `capture_command` (con `{duration}`),
  `stt_command`, `tts_command`, `play_command`, `sample_rate`, `frame_samples` y
  `timeout_s`. Las listas vacías desactivan cada paso; `sample_rate` y
  `frame_samples` deben coincidir con el TTS para sincronizar la boca.
- **Globales**: `idle_state` (por defecto `sentado`), `bubble_ms_per_char` y
  `drag_snap_ms`.

## Desarrollo

```bash
.venv/bin/python -m pytest -q
```

Se trabaja con TDD: cada cambio empieza por un test que falla, sigue con la
implementación mínima y termina con la suite en verde. Para añadir cosas:

- **Otro proveedor**: módulo en `alive/infrastructure/providers/` que cumpla el
  protocolo de `domain/contracts.py`; no tocar la vista.
- **Otra app**: entrada en `[apps]`, sin código nuevo.
- **Otra zona**: entrada en `[zones.nombre]`, sin código nuevo.
- **Otro estado que la IA pueda pedir**: `ALLOWED_STATES` en `domain/orders.py`
  y `STATES` en `domain/animation.py`. Los estados internos (`escuchando`,
  `pensando`, `hablando`, `arrastrado`, `no_molestar`) los decide el motor.
- **Otro widget o gesto**: `alive/ui/`, conectándolo desde `main.build`.

El avatar dibujado es un placeholder: sustituye `_draw` en
`alive/ui/avatar_view.py` por tu sprite, manteniendo `render(frame)` con
`frame.state`, `frame.mouth` (0–1) y `frame.snap_progress` (0–1). El tamaño se
cambia en `_SIZE` y la silueta que acepta clics en `_BODY`/`_HEAD`.

## Comprobación manual

1. Clic en el avatar → se abre el panel; escribe y pulsa Enter → globo y boca.
2. Arrastre → al soltar se ancla a barra o costado con animación; el panel de
   Plasma no se mueve y el avatar sigue al cursor aunque salgas de la ventana.
3. Arrastre, suelta y vuelve a arrastrar antes de 250 ms → no hay salto atrás.
4. «Micrófono» mantenido → transcripción y respuesta; si faltan binarios,
   aviso visible y micrófono oculto.
5. Respuesta con `ABRIR=firefox` → se abre Firefox; `ESTADO=musica` → cambia el
   color; `ZONA=…` → se ignora.
6. Clic en el área vacía alrededor del avatar → pasa a la ventana de debajo.
7. «No molestar» → el avatar deja de recibir clics y vuelve al pulsar de nuevo.
8. «Salir» o `Ctrl+Q` → termina el proceso.

## Solución de problemas

- **No aparece el panel**: haz clic sobre el avatar (no sobre el área vacía que
  lo rodea). Un temblor de hasta 10 px sigue contando como clic.
- **El micrófono no hace nada**: revisa `[voice]` en `config.toml`. Sin
  `whisper-cli`, `piper` y `paplay` la voz no puede funcionar; el aviso al
  arrancar lo indica y el botón se oculta.
- **No se puede cerrar**: usa «Salir» en el panel o `Ctrl+Q`.
- **El arrastre salta o no hace snap**: comprueba `[zones]` y `drag_snap_ms`; el
  snap se anima desde la posición de suelta hasta la zona elegida.
- **No hay `config.toml`**: copia `config.toml.example` como se indica arriba.

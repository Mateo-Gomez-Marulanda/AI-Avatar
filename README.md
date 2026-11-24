# Alive — avatar 2D para Linux/KDE

Alive es un avatar flotante dibujado con GTK3 + GtkLayerShell que conversa con un
CLI de IA y muestra las respuestas en un globo. Vive **debajo** del panel superior:
no tapa los iconos ni desplaza la barra.

Desde el P0 es un asistente conversacional: recuerda el historial, propone acciones
y el avatar decide qué se ejecuta. **La IA nunca decide animaciones ni ejecuta nada
por su cuenta.** Las apps de la whitelist se abren directo; los comandos solo corren
después de que el usuario apruebe el comando exacto.

## Qué hace y qué no hace

**Hace**

- Overlay transparente anclado a zonas de la pantalla (barra, costados o flotante).
- Panel de texto, micrófono de pulsación mantenida (PTT) y botón «No molestar».
- Globos de texto y boca sincronizada con la envolvente RMS del audio.
- Memoria de conversación: mensajes del usuario, respuestas y resultados de acciones.
- Apps permitidas por una whitelist, abiertas sin diálogo ni aprobación.
- Comandos con diálogo de aprobación: comando exacto, qué hace y por qué, con
  timeout y ejecución en segundo plano (salida acotada y registro local).
- Estados locales `pensando`, `esperando` y `ejecutando`; idle rotativo entre
  `sentado` y `parado`; `musica` mientras reproduzca un reproductor MPRIS.
- Cierre limpio con el botón «Salir» o `Ctrl+Q`.

**No hace**

- No incluye ni reemplaza a Veadotube: el renderer es propio.
- No trae modelos locales: delega en OpenCode (o en otro CLI configurable).
- No usa herramientas nativas de OpenCode: el agente `alive` las deniega todas.
- No permite que el modelo pida estados visuales, animaciones ni música: los decide
  el motor local.
- No instala motores de voz: STT/TTS dependen de binarios del sistema.
- No registra atajos globales del sistema.
- No mueve el panel de texto al layer-shell: es una ventana GTK normal.
- No recuerda aprobaciones: cada comando se aprueba una vez.

## Requisitos

- KDE Plasma con Wayland (probado en Plasma 6 / Wayland).
- GTK 3, GtkLayerShell (`GtkLayerShell-0.1.typelib`), PyGObject y pycairo.
- Python 3.11+ (`tomllib`).
- **OpenCode autenticado** (`opencode run`, V2 con `--format json`) y un proveedor
  o modelo con cuota disponible. Copia `.opencode/agents/alive.md` a
  `~/.config/opencode/agents/alive.md`: ese agente deniega todas las herramientas.
  Sin él, OpenCode responde «Agent not found» y no se ejecuta nada.
- `playerctl` opcional para el estado `musica` (consulta MPRIS). Si falta, la música
  queda desactivada y se registra una vez; el resto del avatar funciona igual.
- Para voz: `ffmpeg` (captura), `whisper-cli` (STT), `piper` (TTS) y `paplay`
  (reproducción). Si faltan, el avatar avisa y oculta el micrófono.

En Arch, por ejemplo:

```bash
pacman -S gtk3 gtk-layer-shell python-gobject python-cairo playerctl
```

## Instalación y arranque

```bash
cp config.toml.example config.toml
mkdir -p ~/.config/opencode/agents
cp .opencode/agents/alive.md ~/.config/opencode/agents/alive.md
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest        # solo para desarrollar
PYTHONPATH=. .venv/bin/python -m alive.main --config config.toml
```

`config.toml` está en `.gitignore`: es local y no se versiona; la plantilla
comentada y versionada es `config.toml.example`. `--config` es opcional y por
defecto vale `config.toml`. El ejemplo trae `voice.enabled = true` con rutas de
modelos que probablemente no tengas: ajústalo o pon `enabled = false` para usar
solo texto.

Para usar otro CLI en modo texto, cambia `provider.command` y pon
`provider.output_format = "text"`.

## Uso e interacción

- **Clic sobre el avatar** abre el panel de texto. Se tolera un temblor de hasta
  10 px entre pulsar y soltar; un movimiento mayor se considera arrastre.
- **Panel**: escribe y pulsa Enter o «Enviar». «Micrófono» funciona como PTT:
  mantén pulsado mientras hablas y suelta para transcribir. «No molestar» anima
  el avatar hasta la esquina inferior derecha y deja pasar los clics; vuelve a
  pulsarlo para devolverlo a su posición exacta. «Salir» cierra el programa. El
  panel permanece visible durante el turno y muestra «Pensando…», «Esperando
  permiso…», «Ejecutando…» o «Hablando…»; entrada, enviar y micrófono quedan
  deshabilitados.
- **PTT en el avatar**: mantén pulsado el **botón derecho** sobre el avatar y
  suelta para transcribir. El botón izquierdo sigue abriendo el panel con un clic
  y arrastrando con movimiento; el botón derecho no arrastra. Solo está activo si
  la voz está disponible.
- **«Abre firefox»**: el modelo propone una app de `[apps]` y se abre directo, sin
  diálogo de aprobación. Si el alias no existe, no se abre nada y se avisa.
- **«Ejecuta …»**: el modelo propone un comando y aparece el diálogo con el
  comando exacto, qué hace y por qué, el directorio de trabajo, el timeout y si la
  salida se enviará al modelo. «Ejecutar una vez» lo ejecuta; **Cancelar, Escape,
  cerrar la ventana o vencer el timeout no ejecutan nada**. No hay terminal
  interactiva: `sudo` u otros comandos que pidan contraseña pueden fallar.
- **Arrastre**: pulsa, mueve y suelta. El avatar sigue al cursor aunque este
  salga de la ventana y luego se desplaza con una animación de snap (~250 ms)
  hasta la zona cuyo centro queda más cerca. Empezar otro arrastre cancela el
  snap anterior; un clic no lo cancela.
- **`Ctrl+Q`** cierra el programa cuando el panel tiene el foco.
- **Voz**: la cadena es captura → STT → IA → TTS → PCM → boca. La síntesis y la
  reproducción van en hilos de fondo; la boca se mueve con la envolvente del PCM
  y el turno sigue ocupado («Hablando…») hasta que termina el audio. Si falta
  algún comando se muestra «Voz no disponible: faltan herramientas» y el
  micrófono desaparece. Si la transcripción falla aparece «No pude escuchar»; si
  falla el TTS, la respuesta escrita sigue visible y el error queda en el registro
  y en el estado del panel.

## Cómo fluye la información

```
Texto / PTT
    │
    ▼
InputPanel (ui) ──callbacks──▶ Mediator (application)
                                   ├─▶ Conversation + build_prompt (memoria)
                                   ├─▶ CliProvider + parse_opencode_output ──▶ OpenCode (agente alive)
                                   ├─▶ parse_action (domain) ──▶ AppLauncher (directo)
                                   │                        └─▶ GtkApprover ──▶ ShellCommandExecutor
                                   │                                          └─▶ resultado al historial y al modelo
                                   ├─▶ AnimationEngine (domain) ──▶ Frame
                                   │        ▲
                                   │        └── MusicMonitor + PlayerctlMusicSource ──▶ musica
                                   ├─▶ on_status ──▶ InputPanel.set_busy
                                   └─▶ logging (XDG_STATE_HOME/alive/alive.log)
                                   ▼
                           AvatarView.render (ui) ──▶ layer-shell + cairo
```

La IA responde texto y, como máximo, **un** bloque:

````markdown
```alive-accion
{"tipo": "app", "alias": ["firefox", "code"]}
```
````

o, para comandos:

````markdown
```alive-accion
{"tipo": "comando", "comando": "printf hola", "que_hace": "Imprime hola", "por_que": "El usuario lo pidió"}
```
````

`parse_action` valida el bloque y lo quita del texto visible; el mediador comprueba
los alias contra `[apps]`, pide aprobación para comandos y devuelve el resultado al
modelo para que lo explique. Un bloque malformado o ambiguo no ejecuta nada.
`AnimationEngine.tick()` produce un `Frame(state, mouth, snap_progress)`; `main.py`
lo llama cada 33 ms con `GLib.timeout_add`. Las llamadas al CLI y la ejecución de
comandos y la voz corren en hilos de fondo (`GtkBackgroundRunner`) y vuelven al
hilo GTK; los niveles de la boca se entregan con `GtkLevelTimer`. El PCM de voz
pasa por `BinarySubprocessRunner`, sin decodificarlo a texto.

## Estructura de carpetas

| Ruta | Contribución al desarrollo |
| --- | --- |
| `alive/domain/` | Reglas puras del negocio: `config.py` (TOML y validación), `actions.py` (contrato de acciones, antes `orders.py`), `conversation.py` (memoria), `animation.py` (estados, boca y snap), `geometry.py` (zonas), `contracts.py` (tipos y protocolos). Python puro: ni GTK ni `subprocess`. |
| `alive/application/` | Casos de uso: `mediator.py` (turnos, acciones y errores visibles), `prompt.py` (prompt de sistema e historial), `commands.py` (ejecución con `sh -c`), `music.py` (monitor de MPRIS), `audio.py` (captura/STT/TTS), `apps.py` (whitelist). No contiene widgets. |
| `alive/infrastructure/` | Adaptadores al mundo exterior: `providers/cli.py` (CLI configurable), `providers/opencode.py` (NDJSON y errores), `mpris.py` (`playerctl`), `background.py` (hilos y GLib), `timer.py` (niveles en GTK), `voice_runner.py` (PCM binario), `logging.py` (registro rotatorio 0600). |
| `alive/ui/` | Todo lo visible: `avatar_view.py` (avatar, eventos, globo y snap), `input_panel.py` (texto, PTT y estado ocupado), `approval_dialog.py` (comando exacto y decisión). |
| `alive/main.py` | Raíz de composición: carga la configuración, construye e inyecta dependencias, cablea callbacks y estado, registra el tick y arranca `Gtk.main()`. Es el único lugar que importa todas las capas y GTK. |
| `tests/` | Suite plana de pytest: un archivo por módulo, `support.py` (fakes), `test_structure.py` (imports por capa), `test_smoke_flow.py` (smoke determinista con CLI falso real) y `fixtures/fake_config.toml`. |
| `docs/` | `estructura-proyecto.md` (diseño por capas), `interaccion-y-salida.md` (clic, salida y voz), `movimiento-y-proveedor.md` (anclajes y OpenCode) y `superpowers/plans/` (planes de ejecución: los archivos nuevos se ignoran, aunque algunos planes antiguos siguen versionados). |
| Raíz del repo | `config.toml.example` (plantilla comentada), `.opencode/agents/alive.md` (agente sin herramientas), `plan-de-desarrollo.md` (diseño original) y este README. |
| Ignorados | `.venv/`, `__pycache__/`, `.pytest_cache/`, `.superpowers/`, `superpowers/`, los planes nuevos de `docs/superpowers/` y `config.toml` son entornos, cachés, scratch y configuración local; no forman parte del código. |

Las dependencias apuntan en una sola dirección: `ui`, `application` e
`infrastructure` pueden importar `domain`; `domain` no importa nada de esas capas;
`main.py` importa todas para cablearlas. `test_structure.py` importa los módulos de
cada capa para detectar que la reorganización sigue intacta.

## Configuración

- **Globales**: `idle_states` (lista de estados para el idle, p. ej.
  `["sentado", "parado"]`) e `idle_switch_s` (20 s) sustituyen al antiguo
  `idle_state` singular. También `bubble_ms_per_char` (45), `drag_snap_ms` (250) y
  `quiet_zone` (`"no_molestar"`): zona usada al activar «No molestar».
- **`[provider]`**: `command` es el CLI con el que se habla; el ejemplo usa
  `["opencode", "run", "--format", "json", "--agent", "alive", "--archived"]`.
  `output_format = "json"` parsea el NDJSON de OpenCode; usa `"text"` para otros
  CLIs. `workdir = "~"` fija el directorio de trabajo del CLI (el agente global
  vive en `~/.config/opencode/agents/`). `timeout_s = 90.0`. Ya no existen
  `session_mode`, `session_flag`, `session_id_regex` ni `prompt_template`: el
  historial se envía en cada llamada y el prompt se construye en local.
- **`[apps]`**: whitelist `alias = "comando con argumentos"`. El modelo solo puede
  pedir un alias de esta lista; el comando se divide con `shlex`, nunca pasa por
  un shell.
- **`[commands]`**: `enabled` (bloqueo duro, sin diálogo si es `false`),
  `timeout_s`, `max_output_bytes`, `max_per_turn` (3 comandos por turno),
  `approval_timeout_s` (120 s), `working_dir` y `share_output_with_model`. Si la
  salida no se comparte, el historial no la guarda y el turno termina sin otra
  llamada al modelo; la salida completa queda solo en el registro local.
- **`[conversation]`**: `max_chars` (6000) recorta solo el transcript; el prompt
  de sistema se envía siempre.
- **`[music]`**: `enabled`, `players` (nombres de `playerctl`; `[]` = cualquiera) y
  `poll_s`. Solo el estado `Playing` activa `musica`. El modelo no puede pedirlo.
- **`[zones.nombre]`**: `anchor` (`top`, `left`, `right`, `bottom`,
  `bottom-right`, `floating`), `margin` y, solo para `floating`, `x`/`y`.
  `margin` del anclaje superior es la altura del panel (p. ej. 32 px). El ejemplo
  define `[zones.no_molestar]` con `bottom-right` y `margin = 12`.
- **`[voice]`**: `enabled`, `capture_command` (con `{duration}`), `stt_command`,
  `tts_command`, `play_command`, `sample_rate`, `frame_samples` y `timeout_s`. Las
  listas vacías desactivan cada paso; `sample_rate` y `frame_samples` deben
  coincidir con el TTS para sincronizar la boca.

## Desarrollo

```bash
.venv/bin/python -m pytest -q                       # suite completa
.venv/bin/python -m pytest tests/test_smoke_flow.py -q   # smoke determinista
```

Se trabaja con TDD: cada cambio empieza por un test que falla, sigue con la
implementación mínima y termina con la suite en verde. El smoke usa un script de
Python real lanzado como proceso CLI falso (sin inyección de proveedor desde
Python): emite NDJSON en el formato que consume `parse_opencode_output`, propone
un comando, lo aprueba, lo ejecuta con `ShellCommandExecutor` y comprueba el
segundo turno y el globo final. Es la puerta de aceptación determinista del P0.

Para añadir cosas:

- **Otro proveedor**: módulo en `alive/infrastructure/providers/` que cumpla el
  protocolo de `domain/contracts.py`; no tocar la vista.
- **Otra app**: entrada en `[apps]`, sin código nuevo.
- **Otra zona**: entrada en `[zones.nombre]`, sin código nuevo.
- **Otra acción de la IA**: ampliar `alive/domain/actions.py`, el prompt y el
  mediador; mantener la aprobación para cualquier comando.
- **Otro widget o gesto**: `alive/ui/`, conectándolo desde `main.build`.

El avatar dibujado es un placeholder: sustituye `_draw` en
`alive/ui/avatar_view.py` por tu sprite, manteniendo `render(frame)` con
`frame.state`, `frame.mouth` (0–1) y `frame.snap_progress` (0–1). El tamaño se
cambia en `_SIZE` y la silueta que acepta clics en `_BODY`/`_HEAD`.

## Comprobación manual

1. Conversación de dos turnos: la segunda pregunta conserva la primera.
2. «Pensando…» visible mientras se espera al modelo.
3. «Abre firefox»: se abre directo, sin diálogo.
4. Sin acciones, el idle alterna `sentado` y `parado` cada 20 s.
5. Abrir Spotify (desde el avatar o a mano) y reproducir: el avatar pasa a
   `musica`; pausar o cerrar Spotify lo devuelve a idle. El modelo no puede pedir
   `musica`.
6. «Ejecuta `printf hola`»: aparece el diálogo con comando, qué hace y por qué;
   Cancelar no ejecuta; Ejecutar muestra el resultado y el modelo lo explica.
7. Comando con código de salida distinto de cero: el modelo recibe el error.
8. Timeout de aprobación: se cancela solo.
9. OpenCode sin autenticación o con límite: globo de error claro, sin bloqueo.
10. Segundo mensaje mientras se piensa: no se lanza otra llamada.
11. `config.toml` sin agente `alive`: error claro, no se ejecuta nada.
12. Smoke con CLI falso de extremo a extremo: es la puerta de aceptación
    determinista (`.venv/bin/python -m pytest tests/test_smoke_flow.py -q`).
13. Smoke real con OpenCode: se hará si hay un proveedor autenticado o un modelo
    disponible; si no, se valida el parser con NDJSON real capturado y se deja
    documentado el bloqueo por autenticación. El smoke real no bloquea el P0.
14. `.venv/bin/python -m pytest -q` en verde.

## Solución de problemas

- **OpenCode alcanzó el límite gratuito**: conecta un proveedor o cambia de modelo.
  El avatar muestra el error y sigue respondiendo; no se bloquea.
- **Falta el agente `alive`**: copia `.opencode/agents/alive.md` a
  `~/.config/opencode/agents/alive.md`. No hay fallback al agente `build`.
- **`sudo` u otros comandos interactivos fallan**: no hay TTY. Usa comandos no
  interactivos; el diálogo avisa antes de aprobar.
- **`playerctl` ausente o reproductor distinto**: `musica` queda inactiva y se
  registra una vez. Instala `playerctl` o ajusta `[music].players` al nombre que
  muestra `playerctl -l`.
- **El diálogo de aprobación no recibe el foco en Wayland**: es una ventana
  normal; haz clic en ella. Cancelar, Escape y cerrar equivalen a no ejecutar.
- **No aparece el panel**: haz clic sobre el avatar (no sobre el área vacía que
  lo rodea). Un temblor de hasta 10 px sigue contando como clic.
- **El micrófono no hace nada**: revisa `[voice]` en `config.toml`. Sin
  `whisper-cli`, `piper` y `paplay` la voz no puede funcionar; el aviso al
  arrancar lo indica y el botón se oculta.
- **No se puede cerrar**: usa «Salir» en el panel o `Ctrl+Q`.
- **El arrastre salta o no hace snap**: comprueba `[zones]` y `drag_snap_ms`; el
  snap se anima desde la posición de suelta hasta la zona elegida.
- **No hay `config.toml`**: copia `config.toml.example` como se indica arriba.

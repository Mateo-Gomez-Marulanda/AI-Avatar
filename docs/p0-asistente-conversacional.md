# Diseño: P0 — asistente conversacional con acciones autorizadas

Estado: **aprobado, implementado e integrado en `main` (P0 cerrado)**.
Fecha: 2026-11-23.

## 1. Intención y por qué

Alive ya tiene el overlay, el panel, el motor de estados y un proveedor CLI. El P0
corrige lo que hoy impide usarlo como asistente: memoria de conversación,
feedback de espera, errores visibles, turnos serializados y OpenCode como modelo
conversacional sin herramientas. Además añade acciones de escritorio con una
regla estricta:

- **Las apps de la lista del usuario se abren directo.**
- **Los comandos requieren aprobación explícita**, mostrando el comando exacto,
  qué hace y por qué.

El avatar es el portero. OpenCode solo conversa y propone; no ejecuta nada por su
cuenta.

## 2. Estado actual que motiva el cambio

- `Mediator` solo guarda las respuestas del asistente: el modelo pierde las
  preguntas anteriores del usuario (`alive/application/mediator.py`).
- El contrato `ESTADO`/`ABRIR` no se explica al modelo y `ESTADO` se sobrescribe
  con `speak`.
- No existe el estado `pensando`; una llamada real a OpenCode tardó ~12 s y el
  avatar seguía mostrando `escuchando`.
- `opencode run` arranca el agente `build`, que tiene herramientas propias de
  código.
- `SubprocessRunner` ignora el código de salida y `stderr`; una respuesta vacía
  se muestra como «ok».
- No hay control de turnos concurrentes.
- La voz, la boca sincronizada y el arte real quedan para P1/P2.

## 3. Objetivos

- Conversación con memoria real: mensajes de usuario, asistente y resultados de
  acciones, con roles y recorte por tamaño.
- Prompt de sistema que fija la personalidad, el idioma, la lista de apps y el
  formato de acción.
- OpenCode con un agente sin herramientas, salida JSON y errores legibles.
- Apps de `[apps]` abiertas directo.
- Comandos siempre con aprobación: comando exacto, qué hace y por qué.
- Ejecución de comandos en segundo plano, con timeout, salida capturada y
  proceso en grupo propio.
- Estados locales `pensando`, `esperando` y `ejecutando`, además de los actuales.
- Idle rotativo entre `sentado` y `parado`, decidido por el motor local.
- `musica` activo mientras un reproductor MPRIS configurado esté reproduciendo.
- Turnos serializados: un solo pedido al modelo y un solo comando a la vez.
- Errores visibles para el usuario y registro local para depurar.
- Tests de conversación, parseo, autorización, ejecución, errores y concurrencia.

## 4. No objetivos

- Sincronizar la boca con el audio ni mover la voz fuera del hilo GTK (P1).
- Arte definitivo, parpadeo, respiración o transiciones animadas (P1/P2).
- Usar las herramientas nativas de OpenCode (shell, edición, subagentes).
- Recordar aprobaciones («permitir siempre»). Cada comando se aprueba una vez.
- Reanudar sesiones de OpenCode. El P0 usa historial explícito en cada llamada.
- Visor completo de salida de comandos. En P0 se muestra un resumen y la salida
  queda en el historial y el registro.
- Multi-monitor, panel en layer-shell o atajos globales.

## 5. Anti-metas

- Ejecutar un comando sin que el usuario haya visto el comando exacto.
- Ejecutar apps fuera de la lista del usuario.
- Que OpenCode caiga silenciosamente al agente `build` con herramientas.
- Pasar texto del modelo a un shell sin aprobación.
- Bloquear el hilo GTK con una llamada al modelo o un comando.
- Permitir que el modelo decida animaciones o estados visuales.

## 6. Restricciones

- KDE Plasma sobre Wayland; GTK 3 + GtkLayerShell.
- OpenCode V2 (`opencode run --format json`), con un agente definido por el
  usuario que deniega todas las herramientas.
- En este equipo no hay ninguna integración autenticada de OpenCode y el modelo
  gratuito ya alcanzó su límite. El P0 debe funcionar con un CLI falso en tests
  y mostrar un error claro cuando OpenCode falle; para uso real el usuario deberá
  conectar un proveedor o configurar un modelo disponible.
- Los comandos se ejecutan con `/bin/sh -c` usando el texto exacto mostrado, sin
  terminal interactiva. `sudo` o cualquier comando que pida contraseña puede
  fallar.
- `domain/` sigue siendo Python puro; GTK y subprocess viven en las capas
  externas.
- Cada cambio se escribe primero como test que falla (TDD).

## 7. Enfoques considerados

1. **Contrato JSON + diálogo de aprobación en el avatar (elegido).** OpenCode sin
   herramientas propone una acción en un bloque cerrado; el avatar la valida,
   pide permiso para comandos, ejecuta y devuelve el resultado al modelo.
   Ventaja: el avatar es el portero real, el comando mostrado es el ejecutado y
   todo es testeable. Coste: depende de que el modelo respete el formato y hace
   una llamada extra tras ejecutar.
2. **Herramientas nativas de OpenCode + puente de permisos por ACP/SDK.** Más
   potente y multi-paso, pero acopla el avatar a OpenCode, no garantiza que cada
   comando venga con «qué hace / por qué» y es demasiado grande para P0.
3. **Contrato JSON + aprobación dentro del panel existente.** Menos ventanas,
   pero el panel es una ventana normal con foco frágil en Wayland y espacio
   insuficiente para comandos largos.

Se elige el 1.

## 8. Diseño detallado

### 8.1 Conversación y prompt

Nuevo `alive/domain/conversation.py`:

```python
Message(role: Literal["user", "assistant", "tool"], text: str)

class Conversation:
    def add_user(text: str) -> None
    def add_assistant(text: str) -> None
    def add_tool_result(command: str, exit_code: int, output: str | None) -> None
    def render() -> str
```

- `render()` produce un transcript legible con etiquetas:
  `Usuario:`, `Alive:`, `Resultado del comando ... (código N):`.
- El mensaje del usuario se añade a `Conversation` una sola vez. El prompt final
  es `build_prompt(system_prompt, conversation)`, que devuelve el prompt de
  sistema seguido de `conversation.render()`. No se concatena el mensaje nuevo
  por separado: ya está en el transcript.
- `Conversation` recorta solo el transcript: `[conversation] max_chars` (6000 por
  defecto) no cuenta el prompt de sistema. El prompt de sistema siempre se envía.
  Se conservan siempre el último mensaje y, si hace falta, se trunca con una
  marca.
- El historial incluye las preguntas del usuario y las respuestas limpias del
  asistente. Los bloques de acción no se muestran como texto conversacional,
  pero sí se registra el resultado de la acción como mensaje `tool`.
- Cuando `share_output_with_model = false`, el mensaje `tool` guarda comando y
  código de salida, pero no la salida. Así una llamada posterior tampoco la
  envía. La salida completa queda solo en el registro local.

Nuevo `alive/application/prompt.py` con `build_system_prompt(apps, commands)`:

- Personalidad: «Eres Alive, un asistente de escritorio. Responde en el idioma
  del usuario, con respuestas claras y breves cuando sea posible».
- Regla de acciones: «Nunca digas que ejecutaste algo. Si necesitas una acción,
  propónla y espera la decisión del usuario».
- Lista de apps disponibles con sus alias.
- Esquema exacto del bloque de acción y ejemplos.
- Regla de un solo bloque por respuesta y solo cuando se propone una acción.
- Prohibición de incluir animaciones, estados visuales, sprites o timings.
- Si `[commands].enabled = false`, el prompt indica que no hay ejecución de
  comandos disponible.

El prompt de sistema se envía como primer bloque del texto que recibe el CLI,
porque `opencode run` recibe un mensaje, no un rol `system` separado.

### 8.2 Contrato de acciones

El modelo responde texto normal y, si necesita una acción, **un único** bloque:

````markdown
```alive-accion
{"tipo": "app", "alias": ["firefox", "code"]}
```
````

o

````markdown
```alive-accion
{
  "tipo": "comando",
  "comando": "sudo apt install foo",
  "que_hace": "Instala el paquete foo",
  "por_que": "El usuario pidió usar foo y no está instalado"
}
```
````

Nuevo `alive/domain/actions.py`:

```python
AppAction(aliases: tuple[str, ...])
CommandAction(command: str, what: str, why: str)
ParsedReply(text: str, action: AppAction | CommandAction | None, error: str | None)

def parse_action(reply: str) -> ParsedReply
```

Reglas de validación:

- Se acepta como máximo un bloque `alive-accion`. Si hay más de uno, no se
  ejecuta nada y se muestra «Respuesta ambigua».
- JSON inválido, `tipo` desconocido, campos faltantes, tipos incorrectos o textos
  vacíos: no se ejecuta nada, se muestra un error y se registra.
- `comando` y las explicaciones tienen límites de longitud (comando 2000
  caracteres; explicaciones 1000) para evitar diálogos inmanejables.
- `alias` puede ser un string o una lista de strings. El mediador comprueba cada
  alias contra `[apps]`; si alguno no existe, no se abre ninguno y se avisa.
- El bloque se elimina del texto que se muestra en el globo. Si el texto queda
  vacío, el mediador usa un mensaje por defecto («Necesito tu permiso para
  ejecutar un comando» o «Abriendo…»).
- `ESTADO` y `ABRIR` desaparecen del contrato del modelo. El motor local decide
  los estados. Las apps se piden con `tipo: "app"`.

### 8.3 Flujo del mediador

`Mediator` mantiene un flag `busy`. Mientras está ocupado:

- `submit_text` no lanza otra llamada: muestra «Espera, estoy ocupado» y vuelve.
- `ptt_start`/`ptt_end` se ignoran.
- El panel deshabilita entrada, enviar y micrófono.

Flujo de un turno:

1. Usuario envía texto.
2. Se añade el mensaje `user`, se pasa a `pensando`, `busy=True`, y se llama al
   modelo en segundo plano.
3. Llega la respuesta:
   - Se añade el texto limpio como `assistant`.
   - Sin acción: se muestra el globo, se habla si hay voz y se vuelve a idle.
   - Acción de app: se abren los alias directo, se añade un mensaje `tool`
     («App abierta: …»), se muestra el texto si existe y se vuelve a idle.
   - Acción de comando: si `[commands].enabled = false`, se rechaza sin abrir
     diálogo, se muestra «Ejecución de comandos desactivada» y se termina el
     turno. Si está activa, se pasa a `esperando` y se pide aprobación.
4. Decisión del comando:
   - **Aprobado**: se pasa a `ejecutando`, se ejecuta en segundo plano y, al
     terminar, se añade un mensaje `tool` con comando y código de salida. La
     salida recortada se incluye solo si `share_output_with_model = true`.
   - **Denegado o timeout de aprobación**: se añade un mensaje `tool` («El
     usuario denegó la acción») y se termina el turno sin volver a llamar al
     modelo.
5. Tras un resultado, si `[commands].share_output_with_model = true` y no se
   alcanzó `max_per_turn`, se pasa a `pensando` y se llama al modelo con el
   resultado para que explique lo ocurrido. Su respuesta puede incluir otra
   acción; se repite el flujo.
6. Si se alcanza `max_per_turn` (por defecto 3 comandos por turno), se muestra
   «He ejecutado varias acciones; dime cómo seguir» y se termina el turno. Las
   apps no cuentan para este límite.
7. Ante un error del proveedor o del ejecutor, se muestra un globo con el error,
   se registra, se limpia `busy` y se vuelve a idle.

Estados nuevos en `alive/domain/animation.py`: `pensando`, `esperando`,
`ejecutando`. El motor los acepta y `AvatarView` les da color propio. El resto de
la animación sigue siendo local.

### 8.3.1 Estados locales, idle y música

- `AnimationEngine` recibe `idle_states` (por defecto `["sentado", "parado"]`) y
  `idle_switch_s` (20 s). Mientras el avatar está idle y sin música, rota entre
  esos estados cada intervalo. La rotación la decide el motor; el modelo no la
  pide.
- `engine.idle()` sustituye al antiguo `transition_to(idle_state)`: elige el idle
  actual o `musica` si hay reproducción activa.
- `musica` no se pide por el modelo. Un `MusicMonitor` consulta MPRIS con
  `playerctl` cada `[music] poll_s` segundos y llama a `engine.set_music(active)`.
  Está activo si algún reproductor de `[music] players` está en estado `Playing`.
  Por defecto `players = ["spotify"]`; una lista vacía significa «cualquier
  reproductor». Si falta `playerctl` o no hay reproductores, el estado queda
  inactivo y se registra una vez.
- Mientras se habla, piensa, espera permiso, ejecuta, se arrastra o está en
  `no_molestar`, ese estado manda. Al volver a idle, `musica` reaparece si la
  reproducción sigue activa.
- `playerctl` ya está instalado en este equipo; es una dependencia opcional y se
  documenta en el README.

### 8.4 Autorización y ejecución

Nuevos tipos en `alive/domain/actions.py` y protocolos en
`alive/domain/contracts.py`:

```python
CommandRequest(command: str, what: str, why: str, workdir: str)
CommandResult(exit_code: int, stdout: str, stderr: str, timed_out: bool,
              duration_s: float)

class CommandExecutor(Protocol):
    def run(self, command: str) -> CommandResult: ...

class Approver(Protocol):
    def request(self, request: CommandRequest,
                on_decision: Callable[[bool], None]) -> None: ...
```

`alive/application/commands.py` implementa `ShellCommandExecutor`:

- `subprocess.Popen(["/bin/sh", "-c", command], cwd=workdir,
  stdin=DEVNULL, stdout=PIPE, stderr=PIPE, start_new_session=True)`.
- `communicate(timeout=...)`; al vencer, mata el grupo con `os.killpg` y marca
  `timed_out=True`.
- Captura `stdout` y `stderr` con un límite por flujo (`max_output_bytes`).
- Devuelve código de salida, duración y salidas recortadas.
- No usa `shell=True`; el texto exacto aprobado se pasa a `sh -c`.
- Se ejecuta en un hilo de fondo (`GtkBackgroundRunner`), nunca en el hilo GTK.

`alive/ui/approval_dialog.py` implementa el `Approver`:

- Diálogo modal, centrado y visible, con título «Alive quiere ejecutar un
  comando».
- Aviso: «Revisa el comando. La explicación la generó el modelo».
- Comando exacto en un `Gtk.TextView` de solo lectura con fuente monoespaciada y
  seleccionable; sin interpretar markup.
- «Qué hace» y «Por qué» en etiquetas con wrap.
- Directorio de trabajo, timeout y si la salida se enviará al modelo.
- Aviso de que no hay terminal interactiva: `sudo` o comandos que piden
  contraseña pueden fallar.
- Botones **Ejecutar una vez** y **Cancelar**. El botón por defecto y Escape son
  Cancelar. Cerrar la ventana equivale a Cancelar.
- Timeout de aprobación configurable (`approval_timeout_s`, 120 s por defecto):
  al vencer se cancela y se avisa.
- La decisión se entrega por callback; no se bloquea el bucle GTK con
  `Gtk.Dialog.run()`.

Privacidad: la salida del comando solo se envía al modelo si
`share_output_with_model = true`. El diálogo lo indica antes de aprobar. Si está
desactivado, el mensaje `tool` se guarda sin salida y el turno termina sin otra
llamada al modelo; así el historial de turnos posteriores tampoco filtra esa
salida. La salida completa queda solo en el registro local.

Registro: `logging` con `RotatingFileHandler` en
`$XDG_STATE_HOME/alive/alive.log` (o `~/.local/state/alive/alive.log`), permisos
0600. Se registran aperturas de apps, comandos propuestos, decisiones (aprobado,
denegado, timeout), códigos de salida, duración y errores. La salida completa no
se registra por defecto.

### 8.5 OpenCode

- Nuevo `.opencode/agents/alive.md` en el repo:
  - `mode: primary`.
  - `permissions` con `action: "*"`, `resource: "*"`, `effect: "deny"` para
    bloquear todas las herramientas.
  - Cuerpo breve: «Eres Alive, un asistente de escritorio. Sigue las
    instrucciones del mensaje. No uses herramientas».
- Despliegue: el archivo del repo sirve de referencia y para tests. El uso real
  soportado copia el agente a `~/.config/opencode/agents/alive.md`; así funciona
  desde cualquier directorio. `provider.workdir` (por defecto `~`) es el cwd con
  el que se lanza `opencode run`. Si se apunta al repo, también se descubre el
  agente local, pero la app no depende de que el cwd sea el repo. Si el agente no
  existe, OpenCode devuelve un evento de error «Agent not found»; el proveedor lo
  convierte en un `ProviderError` legible y no se ejecuta nada.
- El comando de ejemplo usa `--archived` para que las sesiones de cada turno no
  ensucien la lista de sesiones del usuario. No se usa `--standalone`: arrancaría
  un servidor privado por turno y no hace falta para este aislamiento.
- `opencode run --format json --agent alive --archived` produce JSON por líneas. Nuevo
  parser en `alive/infrastructure/providers/opencode.py`:
  - Acumula `sessionID` (para registro y futuras mejoras).
  - Si aparece un evento `type: "error"`, lanza `ProviderError` con el mensaje
    del error. Casos especiales: `provider.free-limit` → «OpenCode alcanzó el
    límite gratuito; conecta un proveedor o cambia de modelo»; `Agent not found`
    → «Falta el agente alive».
  - Recoge los `part.type == "text"` del último `messageID` y los concatena.
  - Ignora eventos desconocidos.
  - Si no hay texto, lanza `ProviderError` con un fragmento de la salida.
- `SubprocessRunner` comprueba el código de salida y lanza `ProviderError` con
  `stderr` (recortado) cuando es distinto de cero. Acepta `cwd` opcional.
- El proveedor deja de tener modos de sesión y `prompt_template`; recibe un
  prompt ya construido. `AiProvider.ask(prompt: str) -> AiReply` con
  `AiReply(text, session_id=None)`.
- Se mantiene el modo texto para otros CLIs y el filtro de cabecera de OpenCode
  cuando `output_format = "text"`.

### 8.6 UI

- `InputPanel`:
  - Nuevo `set_busy(busy: bool, status: str = "")` que deshabilita entrada,
    enviar y micrófono, y muestra una etiqueta de estado.
  - `_submit` deja de ocultar el panel al enviar; el panel permanece visible
    durante el turno para mostrar «Pensando…», «Esperando permiso…» o
    «Ejecutando…». El usuario puede cerrarlo con la ventana.
  - `delete-event` oculta el panel en vez de destruirlo.
  - El mediador recibe un callback `status(busy, texto)` cableado desde `main`.
- `AvatarView`: colores para `pensando`, `esperando` y `ejecutando`. Sin cambios
  en arrastre, snap, globo ni región de entrada.
- El globo muestra la respuesta limpia del modelo y resúmenes de acciones
  («Abriendo firefox», «Comando ejecutado (código 0)», «Acción cancelada»).
  La salida completa no se muestra en P0.

### 8.7 Configuración

Nuevo ejemplo de `config.toml`:

```toml
idle_states = ["sentado", "parado"]
idle_switch_s = 20.0
bubble_ms_per_char = 45
drag_snap_ms = 250

[provider]
command = ["opencode", "run", "--format", "json", "--agent", "alive", "--archived"]
output_format = "json"   # "text" para otros CLIs
workdir = "~"            # cwd de opencode; el agente global vive en ~/.config
timeout_s = 90.0

[apps]
firefox = "firefox --new-window"
code = "code"
terminal = "konsole"

[commands]
enabled = true
timeout_s = 30.0
max_output_bytes = 8192
max_per_turn = 3
approval_timeout_s = 120.0
working_dir = "~"
share_output_with_model = true   # true = más cómodo; el diálogo avisa

[conversation]
max_chars = 6000

[music]
enabled = true
players = ["spotify"]   # nombres de playerctl; [] = cualquiera
poll_s = 5.0

[zones.barra]
anchor = "top"
margin = 32

# ... zonas y voz sin cambios
```

Cambios de configuración:

- Se eliminan `session_mode`, `session_flag`, `session_id_regex` y
  `prompt_template`. El P0 usa historial explícito y una sola llamada por turno.
- Se añaden `[commands]`, `[conversation]` y `[music]`.
- `idle_state` singular se sustituye por `idle_states` + `idle_switch_s`.
- `config.toml` pasa a `.gitignore`; solo se versiona `config.toml.example`.
- `config.toml.example` y el README se actualizan con el agente, la autorización,
  los estados nuevos, la música y el requisito de autenticar OpenCode.

## 9. Archivos afectados

| Archivo | Cambio |
| --- | --- |
| `alive/domain/conversation.py` | Nuevo: mensajes, transcript y recorte. |
| `alive/domain/actions.py` | Nuevo: parseo del bloque, acciones y resultados. |
| `alive/domain/contracts.py` | Nuevo `AiProvider.ask(prompt)`, `Approver`, `CommandExecutor`, `CommandRequest/Result`. |
| `alive/domain/animation.py` | Estados `pensando`, `esperando`, `ejecutando`; idle rotativo y flag de música. |
| `alive/domain/config.py` | Nuevas secciones `[commands]`, `[conversation]`, `[music]`; `idle_states`/`idle_switch_s`. |
| `alive/domain/orders.py` | Se elimina; su contrato se sustituye por `actions.py`. |
| `alive/application/prompt.py` | Nuevo: prompt de sistema con apps y esquema. |
| `alive/application/commands.py` | Nuevo: ejecución con `sh -c`, timeout y captura. |
| `alive/application/mediator.py` | Conversación, turnos, aprobación, acciones y errores. |
| `alive/infrastructure/providers/cli.py` | `ask(prompt)`, código de salida, `cwd`, modo texto/JSON. |
| `alive/infrastructure/providers/opencode.py` | Nuevo: parser NDJSON y errores de OpenCode. |
| `alive/infrastructure/mpris.py` | Nuevo: `PlayerctlMusicSource` para `musica`. |
| `alive/infrastructure/background.py` | Sin cambios: el mediador envuelve el trabajo para convertir cualquier excepción en un error visible. |
| `alive/ui/approval_dialog.py` | Nuevo: diálogo de comando y decisión. |
| `alive/ui/input_panel.py` | Estado ocupado, etiqueta de estado y cierre sin destruir. |
| `alive/ui/avatar_view.py` | Colores de los estados nuevos. |
| `alive/main.py` | Cableado de conversación, executor, approver, estado y logging. |
| `config.toml.example`, `.gitignore`, `README.md` | Nueva configuración, agente, flujo y requisitos. |
| `.opencode/agents/alive.md` | Nuevo: agente sin herramientas. |
| `tests/` | Tests nuevos y actualización de los existentes. |

## 10. Pruebas

- `test_conversation.py`: roles, orden, render, recorte, truncado y redacción de
  salida cuando no se comparte.
- `test_animation.py`: rotación de idle, música sobre idle, habla sobre música y
  vuelta al estado correcto.
- `test_music.py`: `playerctl -l`, coincidencia de reproductores, `Playing` frente
  a `Paused`, lista vacía como «cualquiera», binario ausente y error de comando.
- `test_prompt.py`: incluye apps, esquema, reglas y no incluye animaciones.
- `test_actions.py`: app válida, app con alias desconocido, comando válido,
  JSON inválido, campos faltantes, tipos incorrectos, dos bloques y texto limpio.
- `test_mediator.py`:
  - la memoria incluye usuario y asistente;
  - el mensaje del usuario aparece una sola vez en el prompt;
  - `pensando` al enviar;
  - app se abre directo sin aprobación;
  - comando pide aprobación;
  - denegar no ejecuta;
  - aprobar ejecuta y devuelve el resultado al modelo;
  - timeout de aprobación no ejecuta;
  - `[commands].enabled = false` no abre diálogo ni ejecuta;
  - `share_output_with_model = false` no guarda ni envía la salida, ni en el
    turno siguiente;
  - límite de comandos por turno;
  - segundo envío mientras `busy` no llama al modelo;
  - error del proveedor y error inesperado vuelven a idle.
- `test_commands.py`: ejecución simple, código distinto de cero, timeout, límite
  de salida y `cwd`.
- `test_opencode_provider.py`: texto, `sessionID`, evento de error, límite
  gratuito, agente inexistente, salida vacía y código de salida distinto de cero.
- `test_cli_provider.py`: modo texto y `cwd`; se retiran los tests de sesión y
  `prompt_template`.
- `test_approval_dialog.py`: botones, Cancelar por defecto, cierre y timeout.
- `test_input_panel.py`: `set_busy` deshabilita widgets y `delete-event` oculta.
- `test_config.py`: nuevas secciones, validación de `output_format`, eliminación
  de campos viejos.
- `test_structure.py`: imports actualizados.
- Smoke con CLI falso: un script que devuelve un bloque de comando; un approver
  falso aprueba; un executor falso registra; se comprueba el flujo completo.

## 11. Verificación manual

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
    determinista.
13. Smoke real con OpenCode: se hará si hay un proveedor autenticado o un modelo
    disponible; si no, se valida el parser con NDJSON real capturado y se deja
    documentado el bloqueo por autenticación. El smoke real no bloquea el P0.
14. `pytest -q` en verde.

## 12. Riesgos y decisiones abiertas

- **OpenCode sin proveedor autenticado**: en este equipo el modelo gratuito ya
  está limitado. El P0 se puede desarrollar y probar con un CLI falso, pero el
  uso real requiere que el usuario conecte un proveedor o configure un modelo.
  No se puede resolver desde el código del avatar.
- **El agente `alive` debe existir**: se entrega en `.opencode/agents/` y se
  documenta la copia global. Si falta, el error es visible y no hay fallback a
  `build`.
- **Comandos con privilegios del usuario**: la aprobación es la única barrera.
  El diálogo debe ser claro y no debe ocultar el comando exacto.
- **Salida enviada al modelo**: por defecto `share_output_with_model = true`
  (la opción más cómoda), con aviso en el diálogo. La salida puede contener datos
  sensibles y viaja al proveedor del modelo; se puede desactivar.
- **Comandos interactivos**: sin TTY, `sudo` y similares pueden fallar. Se avisa
  en el diálogo; no se añade terminal en P0.
- **Foco del diálogo en Wayland**: es una ventana normal; si el compositor no la
  enfoca, el usuario puede hacer clic. Se verificará manualmente.
- **El modelo puede mentir en «qué hace / por qué»**: el diálogo avisa de que la
  explicación es del modelo; el usuario debe revisar el comando.
- **Formato del modelo**: si no respeta el bloque, no se ejecuta nada. Es un
  fallo seguro.
- **Música depende de MPRIS**: hace falta `playerctl` y que el nombre del
  reproductor coincida (`spotify`, `brave`, etc.). Solo `Playing` activa
  `musica`; pausado no. Si falta `playerctl` o no hay reproductores, se registra
  y la música queda desactivada.

## 12.1 Decisiones cerradas durante la revisión

- **Idle y música locales**: `sentado`/`parado` rotan como idle; `musica` se
  activa por MPRIS con `playerctl` y nunca por el modelo.
- **Privacidad por comodidad**: `share_output_with_model = true` por defecto,
  con aviso en el diálogo y opción de desactivarlo.
- **Privacidad coherente**: si `share_output_with_model = false`, el mensaje
  `tool` se guarda sin salida; no se filtra en turnos posteriores.
- **Un solo lugar para el mensaje nuevo**: el usuario se añade una vez a
  `Conversation`; `build_prompt()` solo antepone el prompt de sistema al
  transcript. No hay duplicación.
- **Agente global y cwd explícito**: el uso real copia el agente a
  `~/.config/opencode/agents/`; `provider.workdir` fija el cwd de OpenCode.
- **Sesiones archivadas**: el comando de ejemplo usa `--archived` para no
  ensuciar la lista de sesiones.
- **`[commands].enabled = false` es un bloqueo duro**: el mediador rechaza la
  acción sin mostrar diálogo.
- **`max_chars` mide solo el transcript**: el prompt de sistema siempre se envía.
- **El smoke real con OpenCode es condicional**: la aceptación determinista usa
  el CLI falso; el parser se valida con NDJSON real.

## 13. Lo que queda al constructor

- Elegir los textos exactos del prompt de sistema y del diálogo.
- Decidir si el resumen de salida se muestra en el globo o solo en el panel.
- Ajustar límites por defecto (timeout, salida, historial, aprobación) si la
  práctica muestra que son incómodos.
- Orden de commits y verificación final, con TDD.
- Actualizar `plan-de-desarrollo.md` con las decisiones nuevas si se considera
  necesario; este documento es la referencia del P0.

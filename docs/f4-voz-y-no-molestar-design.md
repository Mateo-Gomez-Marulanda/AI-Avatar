# Diseño F4: voz no bloqueante y zona «no molestar»

Estado: **pendiente de aprobación**.
Fecha: 2026-11-24.

## 1. Intención y por qué

El plan original dejó F4 (voz) como fase futura. El código ya tiene captura,
STT, TTS, reproducción y boca, pero `VoiceService.speak()` corre en el hilo GTK,
emite los niveles **después** de que `paplay` termine y el mediador cierra el
turno antes de que acabe la reproducción. Además, el PTT solo existe en el panel
y «no molestar» únicamente anula clics: el avatar se queda donde estaba.

Queremos que la voz sea uso real sin bloquear la interfaz, que la boca acompañe
la reproducción, que el turno termine al terminar de hablar y que «no molestar»
mueva el avatar a una esquina discreta y lo devuelva al desactivarlo. El arte
definitivo queda fuera de alcance: se integrará cuando el sistema sea funcional.

## 2. Objetivos

- Síntesis y reproducción de voz en hilos de fondo; ningún subprocess de voz en
  el hilo GTK.
- PCM de captura y TTS tratado como bytes, sin decode/encode a texto.
- Niveles de boca entregados en el hilo GTK mientras suena el audio, con un
  temporizador inyectado y determinista en tests.
- El turno sigue ocupado («Hablando…») hasta que termina la reproducción; los
  errores de TTS no rompen la respuesta escrita.
- PTT también sobre el avatar, con botón derecho pulsado/soltado, sin quitar el
  clic ni el arrastre con botón izquierdo.
- «No molestar» anima el avatar hasta la esquina inferior derecha, deja pasar
  los clics y lo devuelve a su zona anterior al desactivarse.
- Cobertura con tests nuevos y suite completa en verde.

## 3. No objetivos

- Instalar `whisper-cli`, `piper`, `espeak-ng` ni modelos. La app seguirá
  avisando y ocultando el micrófono cuando falten herramientas.
- Sustituir el placeholder cairo por arte, añadir parpadeo/respiración o
  cambiar `Frame` (estado, boca, progreso de snap).
- Atajos globales del sistema, cancelación de una respuesta en curso, streaming,
  multi-monitor o detección automática de pantalla completa.
- Cambiar el contrato `alive-accion`, la memoria de conversación ni la
  aprobación de comandos de P0.

## 4. Anti-metas

- Que un fallo de voz deje el panel bloqueado para siempre.
- Que un turno anterior pueda mover la boca o cerrar el turno de otro posterior.
- Que «no molestar» tape iconos del panel, mueva el avatar sin animación o
  pierda la posición anterior del usuario.

## 5. Restricciones

- GTK 3 + GtkLayerShell sobre Wayland: la posición se controla con anclajes y
  márgenes, nunca con `window.move()`.
- `domain/` es Python puro; `application/` no importa GTK; `infrastructure/`
  adaptada a GLib; `main.py` es la raíz de composición.
- `GtkBackgroundRunner` entrega un único resultado al hilo principal mediante
  `GLib.idle_add`: no sirve para entregar niveles progresivos desde el worker.
- Los tests son planos en `tests/`; cada cambio se escribe primero como test que
  falla. El comando de verificación es `.venv/bin/python -m pytest -q`.

## 6. Enfoques considerados

### Voz

1. **Un único hilo de fondo** que sintetiza, reproduce y emite niveles con
   `GLib.idle_add` por nivel. Menos piezas, pero mezcla timing de audio con
   entrega de eventos GTK y necesita protección extra contra turnos solapados.
2. **Etapas explícitas** (elegida): síntesis en fondo, reproducción en fondo y
   niveles programados en GTK mediante un temporizador inyectado. Más piezas,
   pero cada etapa es testeable con fakes y el turno se cierra una sola vez.

### PTT en el avatar

1. **Pulsación larga con botón izquierdo.** Compite con el umbral de arrastre
   (10 px) y obliga a distinguir clic, arrastre y pulsación retenida.
2. **Botón derecho pulsado/soltado** (elegida): el botón izquierdo conserva su
   semántica y no se añaden atajos globales. El micrófono del panel sigue como
   alternativa visible.

### «No molestar»

1. **Zona flotante con coordenadas fijas.** Simple, pero no se adapta al monitor.
2. **Nuevo anclaje `bottom-right`** (elegida): el compositor calcula la esquina;
   se guarda la zona anterior y se anima ida y vuelta con el mecanismo de snap
   existente.

## 7. Decisiones de implementación

### 7.1 Voz por etapas

- **PCM binario:** `SubprocessRunner` sigue siendo de texto para el provider de
  IA. La voz usa `BinarySubprocessRunner` en
  `infrastructure/voice_runner.py`, que devuelve `result.stdout` sin decodificar.
  `VoiceService` elimina `_as_bytes`/`_as_text` para audio: `record()` y
  `synthesize()` devuelven bytes y `transcribe()` recibe bytes. Sin esto,
  `piper --output_raw` y `ffmpeg -f s16le` se corrompen al re-codificar.
- `VoiceService` deja de dormir y de llamar a `on_level` en el hilo de trabajo.
  Expone `synthesize(text) -> bytes`, `play(pcm) -> None`, `envelope(pcm)` y
  `speak_async(text, on_level, on_ready, on_done, background, timer)`.
- `speak_async` envía la síntesis a `background.run`. En el callback (hilo GTK)
  calcula la envolvente, avisa `on_ready(duration_s)` con la duración real del
  PCM, lanza la reproducción también en fondo y programa los niveles con
  `timer.after(delay_s, callback)`; cada callback es de un solo disparo. Al
  terminar la reproducción se cancelan los niveles pendientes, se emite un nivel
  0 para cerrar la boca y se llama a `on_done` exactamente una vez.
- Los trabajos de fondo devuelven un resultado con `error` en vez de lanzar,
  para que `done` siempre llegue aunque falle TTS o `paplay`. Un contador de
  generación cancela niveles pendientes y descarta callbacks de una síntesis
  anterior; es defensa, no se prevé una nueva jugada porque `busy` bloquea
  las entradas.
- `LevelTimer` es un protocolo en `domain/contracts.py`; `GtkLevelTimer` en
  `infrastructure/timer.py` usa `GLib.timeout_add`. Los tests usan un temporizador
  falso que dispara manualmente.
- `AnimationEngine.speak()` admite `duration_s` opcional y gana
  `set_speech_duration(duration_s, now)` y `end_speech(now)`. El mediador usa
  `on_ready` para fijar la duración real y `on_done` para forzar el fin del
  estado «hablando»; así no queda boca falsa si el audio es más corto ni estado
  idle si es más largo.
- `Mediator._display()` llama a `speak_async`; mantiene `busy = True`, estado
  «Hablando…» y avisa «Hablando…» en el panel durante la reproducción. El turno
  termina en `on_done`. Si no hay TTS/reproductor, `on_ready(0.0)` y `on_done()`
  se llaman de forma inmediata y el comportamiento actual queda intacto.
- `load_config` valida `voice.sample_rate > 0`, `voice.frame_samples > 0` y
  `voice.timeout_s > 0`. El valor por defecto sigue siendo 16000 Hz / 1024 muestras.

### 7.2 PTT en el avatar

- `AvatarView` atiende `button == 3`: al pulsar llama a `on_ptt_start()` y agarra
  el puntero; al soltar libera el agarre y llama a `on_ptt_end()`. El botón 1
  sigue igual. Si `_click_through` está activo, no hace nada.
- `Mediator.ptt_end(held_seconds=None)` calcula la duración con su reloj cuando
  no se le pasa un valor; el panel sigue pasando la suya.
- `main.build` cablea los callbacks de PTT del avatar solo si la voz está
  disponible; si faltan herramientas, el botón derecho no hace nada.
- README documenta el gesto y la alternativa del panel.

### 7.3 «No molestar»

- Se añade el anclaje `bottom-right` a `ANCHORS`, a `zone_rect` y a
  `_apply_zone` (BOTTOM + RIGHT anclados, márgenes `zone.margin`).
- `Config` gana `quiet_zone: str = "no_molestar"`. `config.toml.example` define
  `[zones.no_molestar]` con `anchor = "bottom-right"` y `margin = 12`. Si el
  usuario no define esa zona, la vista usa un `Zone("bottom-right", margin=12)`
  sintético: no hay fallo de arranque.
- `AvatarView` expone `current_rect()` y `current_zone()`, y hace que
  `snap_to(name | Rect)` sea animado: toma el rectángulo actual como origen,
  fija el destino y deja que `render` aplique la interpolación con
  `frame.snap_progress`. El destino final se aplica al llegar a 1.0, igual que
  en el arrastre. Al salir de quiet se restaura el **rectángulo exacto** donde
  estaba el avatar, no solo el nombre de la zona: un arrastre libre no debe
  perder su posición.
- `AnimationEngine` gana `set_quiet(active, now)` y `begin_snap(now)`;
  `end_drag` delega en `begin_snap`. `set_quiet(True)` guarda el estado y el
  `speaking_until` previos; `set_quiet(False)` los restaura si seguía un turno,
  o vuelve a idle en caso contrario. Así, apagar «no molestar» a mitad de una
  respuesta no la corta visualmente. `idle()` devuelve `no_molestar` cuando está
  activo y el rotor de estados idle se detiene. Los eventos de música no cambian
  el estado mientras quiet está activo.
- Quiet domina **idle y música**, no los estados de turno (`pensando`,
  `esperando`, `ejecutando`, `hablando`): durante una respuesta el avatar sigue
  mostrando el estado de la interacción; al terminar, vuelve a `no_molestar`.
  El frame `arrastrado` durante el snap es transitorio y está decidido por el
  motor local.
- `Mediator.toggle_no_molestar()` guarda el rectángulo actual al entrar, anima
  hacia `config.quiet_zone`, activa click-through y pone el estado; al salir
  anima de vuelta al rectángulo guardado y restaura la interacción.

## 8. Archivos afectados

| Archivo | Cambio |
| --- | --- |
| `alive/application/audio.py` | Síntesis, reproducción y niveles por etapas; resultado con error y generación. |
| `alive/application/mediator.py` | `speak_async`, turno hasta fin de audio, PTT sin argumento y toggle quiet con zona. |
| `alive/domain/contracts.py` | `LevelTimer`, `SpeechResult` y ajustes de protocols. |
| `alive/domain/animation.py` | Modo quiet y `begin_snap`. |
| `alive/domain/config.py` | `quiet_zone`, anclaje `bottom-right`, validación de voz. |
| `alive/domain/geometry.py` | Rectángulo de `bottom-right`. |
| `alive/infrastructure/timer.py` | `GtkLevelTimer` (nuevo). |
| `alive/infrastructure/voice_runner.py` | `BinarySubprocessRunner` para PCM (nuevo). |
| `alive/ui/avatar_view.py` | PTT con botón derecho, `current_zone()`, snap animado y anclaje de esquina. |
| `alive/main.py` | Cableado del temporizador, PTT condicional y callbacks de quiet. |
| `config.toml.example`, `README.md` | Zona quiet, gesto PTT y turno «Hablando…». |
| `tests/` | Tests nuevos en audio, mediador, animación, config, geometría, vista y main. |

## 9. Pruebas y verificación

- **Rojo → verde** por comportamiento: PCM binario sin corromper, niveles
  programados sin dormir, `done` único tras error de TTS/reproducción, duración
  real de «hablando», turno ocupado hasta terminar de hablar, PTT derecho con
  clic/arrastre intactos, quiet con click-through, retorno al rectángulo exacto
  y anclaje inferior derecho.
- Smoke determinista existente (`tests/test_smoke_flow.py`) y uno nuevo de voz
  con CLI falso para la cadena captura → STT → TTS → niveles → fin de turno.
- `.venv/bin/python -m pytest -q` en verde; los dos warnings GTK preexistentes
  no bloquean.
- Comprobación manual (fuera de tests): con binarios reales, la boca acompaña
  la voz y «no molestar» deja el avatar en la esquina inferior derecha.

## 10. Lo que queda al implementador

- Orden de tareas y commits: se propone voz, PTT y quiet en tareas separadas,
  con un commit por comportamiento verificable; el implementador puede ajustar
  el orden si evita conflictos.
- Redactar los textos concretos del panel («Hablando…») y del README.
- La rotación de estados idle queda detenida mientras quiet esté activo; se
  reanuda al salir desde el estado idle normal. Si se apaga quiet durante un
  turno, se restaura el estado previo hasta `on_done`.
- El temporizador usa el reloj GTK; la envolvente se calcula del PCM generado,
  no de un monitor de PulseAudio. Es una decisión propia: evita otra dependencia
  y mantiene la boca determinista con el audio sintetizado.
- No existe una acción que inicie una síntesis nueva antes de que termine la
  anterior: el contador de generación es solo defensa ante callbacks rezagados.

# Plan de desarrollo — Avatar de escritorio «Alive»

Estado: **borrador, pendiente de aprobación**.
Fecha: 2026-11-23.

## 1. Intención y por qué

Crear un avatar 2D propio que viva sobre el escritorio de Linux (KDE Plasma / Wayland), sirva de interfaz visible para un modelo de IA y pueda abrir aplicaciones. El avatar tiene personalidad propia mediante estados y animaciones, pero **la IA no decide cómo se ve ni cuánto cuesta animarlo**: un intermediario local traduce las respuestas del modelo a estados, movimiento de boca, globos de texto y apertura de apps.

La motivación central es que el modelo solo gaste tokens en conversar. Toda la coreografía es determinista y local.

## 2. Metas, no metas y anti-metas

### Metas
- Avatar transparente siempre encima del escritorio, sobre ventanas y compatible con la barra superior.
- Estados: sentado, parado, escuchando, hablando, escuchando música, siendo arrastrado (y ampliables por configuración).
- Globo de texto con la respuesta; boca sincronizada cuando haya voz.
- Entrada por texto y por botón de micrófono (push-to-talk).
- Apertura de aplicaciones desde una lista blanca configurable.
- Arrastre con el cursor y animación de movimiento, con ajuste («snap») a zonas del escritorio.
- Zonas/«secciones» propias del avatar para no molestar: anclaje arriba/izquierda/derecha/abajo y modo «no molestar» sin interceptar clics.
- Proveedor de IA configurable por el usuario (CLI: opencode, Claude Code u otro). Sin modelos locales por ahora.

### No metas (versión 1)
- Hacer clic o escribir dentro de las aplicaciones (solo abrirlas).
- Ejecutar comandos de shell arbitrarios pedidos por el modelo.
- Que la IA elija, describa o solicite animaciones específicas.
- Modelos locales, GPU, Veadotube o cualquier renderer de terceros.
- Multi-monitor avanzado: se usa el monitor principal; dejar configurable.

### Anti-metas (lo que haría que esto fracase aunque funcione)
- Que el avatar robe el foco, tape ventanas o intercepte clics por defecto.
- Que el prompt del IA incluya sprites, timings o instrucciones de animación.
- Que cambiar de modelo de IA obligue a tocar el motor de animación.

## 3. Restricciones del entorno

- KDE Plasma sobre **Wayland** (`XDG_SESSION_TYPE=wayland`); hay un `DISPLAY=:1` de XWayland, pero **no** hay `xdotool`, `wmctrl`, `ydotool` ni `wtype`.
- Disponible: `python3` con `gi` (GTK 3.24), D-Bus (`gdbus`, `busctl`), `libgtk-layer-shell.so`, `grim`, `import`, `ffmpeg`, `pactl`/`wpctl`.
- GObject Introspection tiene disponible `GtkLayerShell` versión `0.1` (verificado: `gi.require_version("GtkLayerShell", "0.1")` funciona). No hace falta `ctypes` ni instalar paquetes extra para layer-shell.
- No hay TTS/STT instalados (`espeak-ng`, `piper`, `whisper` ausentes).
- No hay arte del personaje ni commits en el repositorio (solo el binario descargado de Veadotube, que **no se usará**).

Consecuencia técnica importante: en Wayland un surface de layer-shell **no se coloca con `window.move()`**. La posición se controla con `anchor` + `margin` respecto al monitor. El arrastre se implementará actualizando esos márgenes, no moviendo la ventana.

## 4. Enfoques considerados

1. **GTK 3 + layer-shell en Python** *(elegido)*. Ventana transparente real sobre KDE, anclajes a barra/costados, input-region para dejar pasar clics, todo en un proceso, D-Bus y `Gio` para lanzar apps. Contra: las animaciones se dibujan a mano y hay que verificar el input-region en el spike inicial.
2. **Tauri/Electron con ventana transparente**. Frontend web para globos y SVG; iteración rápida y animaciones ricas. Contra: las ventanas siempre encima y los anclajes en Wayland son frágiles, y añade un puente con el escritorio.
3. **Godot 4**. Mejor editor de estados/animaciones. Contra: integración con layer-shell, voz y CLI más pesada para lo que se necesita.

Se eligió el 1 porque es el único que garantiza flotar sobre KDE Plasma sin pelear con el compositor.

## 5. Arquitectura acordada

```
[ Campo de texto / botón PTT ]
              |
              v
      +-------------------+
      |  INTERMEDIARIO    |  máquina de estados, turnos, globo,
      |  (dueño del ciclo) |  boca, zonas, whitelist de apps
      +---------+---------+
         |             |
         v             v
  +-------------+  +------------------+
  | MOTOR DE    |  | ADAPTADOR IA CLI |  opencode / Claude Code / otro
  | ANIMACIÓN   |  | configurable     |  prompt -> subprocess -> texto
  +-------------+  +------------------+
         |
  +-------------+  +------------------+
  | VOZ (STT/TTS)| | GTK + layer-shell|
  +-------------+  +------------------+
```

### 5.1 Motor de animación
- Dueño exclusivo de estados, sprites, duraciones, easing y del globo de texto.
- Estados iniciales: `sentado`, `parado`, `escuchando`, `hablando`, `musica`, `arrastrado`, `no_molestar`.
- Transiciones por temporizador y por eventos del intermediario; nunca por decisión del modelo.
- Arrastre: `button-press/motion/release`; durante el arrastre entra en `arrastrado`; al soltar hace snap al borde/zona más cercana con animación de aterrizaje.
- Anclas: barra superior (con `exclusive_zone = 0` para no desplazar el panel), izquierda, derecha, abajo y flotante.
- Modo «no molestar»: mueve el avatar a su franja propia y anula su región de entrada (click-through).
- Boca: sigue la envolvente de RMS del audio TTS (PulseAudio monitor + `ffmpeg`) o, si no hay audio, un temporizador proporcional al número de caracteres.

### 5.2 Intermediario
- Único que puede pedir cambios de estado y abrir apps.
- Contrato con la IA: conjunto **cerrado** de órdenes que el modelo puede emitir: `ESTADO=<sentado|parado|musica>` y `ABRIR=<alias>`. Nada más. Fuera de la lista se ignoran y se registran. `ZONA=` queda reservado al usuario y al intermediario: el modelo nunca decide dónde se coloca el avatar.
- El intermediario **deriva por su cuenta** `escuchando`, `pensando` y `hablando`, y también gestiona `arrastrado` y `no_molestar`. La IA solo puede pedir estados gruesos, nunca frames, timings ni formato del globo. Las órdenes `ESTADO=...` explícitas son temporales y caducan.
- Mantiene la cola de globos, evita solapamientos y decide cuándo volver al estado base.

### 5.3 Adaptador de IA configurable
- Config por archivo (TOML/JSON): comando base del CLI, plantilla de prompt, argumentos, timeout, formato de salida y `session_mode`.
- `session_mode=resume` (por defecto cuando el CLI lo soporta) reanuda una sesión existente para no reenviar todo el historial en cada turno; `session_mode=oneshot` lanza un proceso nuevo con el historial en el prompt. El modo se elige por proveedor en la configuración, no en el código del avatar.
- Limpieza de ANSI, manejo de streaming o salida final, cancelación y errores.
- El prompt **no** incluye información de animación: solo la conversación y las órdenes válidas permitidas.
- No hay dependencia con proveedores locales ni con una librería específica de modelo.

### 5.4 Apps
- Lista blanca `alias -> comando` en configuración (por ejemplo `firefox`, `code`, `terminal`).
- Lanzamiento con `Gio.AppInfo`/`subprocess` sobre la whitelist; nunca `shell=True` con texto del modelo.
- Sin clic/escritura dentro de apps en la v1.

### 5.5 Voz
- Botón push-to-talk; al pulsar, estado `escuchando`.
- STT y TTS configurables por proveedor: opciones iniciales a evaluar en el spike (`faster-whisper` tiny en CPU o servicio en la nube; `piper`/`espeak-ng` o TTS en la nube). Instalación vía `apt`/`pip` según lo que funcione sin GPU.
- La respuesta se muestra siempre en un globo, con o sin voz.

### 5.6 Arte
- No hay sprites. Se usarán placeholders vectoriales/capas generados localmente con los estados mínimos; el usuario podrá sustituirlos por arte propio sin tocar código. **Decisión del autor**, revisable.

### 5.7 Entrada, foco y «no molestar»
- El campo de texto vive en un panel compacto que solo pide foco de teclado cuando el usuario lo abre (clic en el avatar/globo o atajo configurado). El surface de layer-shell **no roba el foco** por defecto: `keyboard_interactivity` permanece desactivado hasta que se pide.
- El botón de micrófono es de **pulsación mantenida** («push-to-talk») sobre el propio avatar; no se usa un atajo global del sistema en la v1.
- Región de entrada activa: la silueta/zona opaca del avatar y los widgets. El resto del surface deja pasar los clics a las ventanas de debajo. Al arrastrar, la región sigue al avatar; en modo «no molestar» queda vacía.
- Anclaje en la barra superior: el avatar queda **justo debajo del panel** (su borde superior coincide con el borde inferior del panel), con `exclusive_zone = 0`, sin cubrir iconos ni desplazar la barra. El margen es configurable y equivale a la altura del panel.
- «No molestar» es **manual** en la v1: interruptor del usuario que reposiciona al avatar en su zona propia y anula la entrada. No silencia globos ni voz por defecto (se podrá configurar por separado). La detección automática de pantalla completa queda para una fase posterior.

## 6. Fases y trazabilidad

| Idea del usuario | Sección | Fase |
|---|---|---|
| Avatar propio, sin Veadotube | 4, 5 | F1 |
| Estados sentado/parado/música | 5.1 | F1 |
| Arrastre con animación | 5.1 | F2 |
| Barra superior, costados, superposición, zonas/no molestar | 5.1, 5.2 | F2 |
| Globo de texto con la respuesta | 5.1, 5.2 | F3 |
| Respuesta por voz + boca | 5.1, 5.5 | F4 |
| Texto y botón de micrófono | 5.2, 5.5 | F3, F4 |
| Abrir aplicaciones | 5.4 | F5 |
| Animaciones decididas fuera de la IA, vía intermediario | 5.2, 5.3 | F1–F3 |
| IA configurable por usuario, CLI actual, sin local | 5.3 | F3 |
| Archivo de plan con trazabilidad | todo | este documento |

### Fases
- **F0 — Spike (descartable).** Verificar en esta máquina: layer-shell transparente sobre KDE, anclaje a barra sin desplazarla, input-region/click-through y arrastre vía márgenes. No se conserva el código del spike.
- **F1 — Overlay y motor de estados.** Ventana transparente, estados base y cambio por temporizador. Criterio: el avatar aparece sobre las ventanas y cambia de estado sin IA.
- **F2 — Zonas y arrastre.** Anclajes, snap, animación de movimiento y modo no molestar. Criterio: se puede arrastrar y dejar en la barra o un costado sin tapar ni bloquear.
- **F3 — Conversación por texto.** Campo de texto, adaptador CLI configurable, globo y transiciones `escuchando/pensando/hablando`. Criterio: una pregunta produce respuesta en globo; el prompt no contiene animación.
- **F4 — Voz.** PTT, STT/TTS configurables, boca por envolvente o temporizador. Criterio: hablar por micrófono genera respuesta en voz y globo, y la boca se mueve sin intervención del modelo.
- **F5 — Apps y pulido.** Whitelist, apertura, manejo de errores, tests del intermediario, documentación de configuración y de cómo cambiar de proveedor.

## 7. Decisiones registradas

| Fecha | Decisión | Origen |
|---|---|---|
| 2026-11-23 | No usar Veadotube; renderer propio | Usuario |
| 2026-11-23 | Stack GTK 3 + layer-shell en Python (opción 1) | Usuario |
| 2026-11-23 | El motor de animación decide; IA solo órdenes al intermediario | Usuario |
| 2026-11-23 | Globo de texto y voz, con boca animada | Usuario |
| 2026-11-23 | Entrada por texto y botón PTT | Usuario |
| 2026-11-23 | Proveedor IA configurable vía CLI; sin modelos locales | Usuario |
| 2026-11-23 | Anclaje a barra/costados, superposición y zonas para no molestar | Usuario |
| 2026-11-23 | Arrastre por márgenes de layer-shell, no `window.move()` | Decisión técnica del autor |
| 2026-11-23 | v1 solo abre apps; sin clic/escritura dentro de ellas | Decisión del autor, derivada del alcance |
| 2026-11-23 | Placeholders vectoriales hasta que haya arte propio | Decisión del autor |
| 2026-11-23 | Documento en `plan-de-desarrollo.md` en la raíz | Usuario |
| 2026-11-23 | El modelo puede pedir `ESTADO` grueso y `ABRIR`; `ZONA` y todo detalle visual quedan fuera de su alcance | Resolución del diseño a partir de tus mensajes |
| 2026-11-23 | Sesión CLI reanudable por defecto; modo de una sola llamada configurable por proveedor | Decisión del autor (objetivo: ahorrar tokens) |
| 2026-11-23 | Panel de texto con foco bajo demanda; PTT en el avatar; clics solo sobre avatar/widgets | Decisión del autor |
| 2026-11-23 | Avatar justo debajo del panel sin cubrirlo; «no molestar» manual sin silenciar | Decisión del autor (corregida por geometría: un avatar alto no cabe encima del panel) |

## 8. Lo que queda para el implementador

- Convertir este diseño en un plan de ejecución detallado (tareas, orden y criterios de verificación) tras la aprobación.
- Resolver durante F0 los detalles técnicos marcados como spike: click-through real (y su alternativa de asa de arrastre si Wayland no respeta la región de entrada) y ruta de audio para TTS.
- Elegir los flags concretos de `opencode`/Claude Code para `session_mode=resume` al implementar el adaptador en F3.
- Elegir los motores STT/TTS concretos y las apps de la whitelist inicial; ambos quedan parametrizables para no bloquear el diseño.
- Sustituir los placeholders por arte definitivo cuando el usuario lo aporte.

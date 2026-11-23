# Diseño corto: interacción, salida y voz disponible

## Intención

Arreglar tres síntomas reportados por el usuario sobre el avatar en KDE/Wayland:
no hay forma de cerrarlo, el panel no se abre ni responde, el micrófono parece
roto y el arrastre no hace snap y da saltos. Es una corrección de comportamiento,
no un rediseño.

## Objetivos

- Poder cerrar la aplicación desde el panel con un botón «Salir» y con Ctrl+Q.
- Que un clic normal abra siempre el panel, aunque haya unos píxeles de temblor.
- Que un arrastre siga al cursor aunque este salga del avatar y termine con una
  animación de snap hasta la zona elegida, sin saltos.
- Que la voz no falle en silencio: si faltan los comandos configurados, el
  micrófono se oculta y se avisa; si una transcripción falla, se muestra un
  globo de error.

## No objetivos

- Instalar motores STT/TTS (en esta máquina no hay `whisper-cli`, `piper`,
  `espeak-ng` ni equivalentes).
- Mover el panel al layer-shell ni cambiar la arquitectura por capas.
- Tocar el contrato cerrado `ESTADO` / `ABRIR`, las zonas ni las animaciones
  base.
- Añadir atajos globales del sistema.

## Restricciones

- GTK 3 + GtkLayerShell sobre Wayland: la posición se controla con márgenes,
  nunca con `window.move()`.
- `main.py` sigue siendo la raíz de composición y puede importar GTK/GLib.
- Tests planos en `tests/`; cada arreglo se escribe primero como test que falla.

## Approaches considerados

1. **Arreglo quirúrgico (elegido).** Corregir el umbral click/arrastre, agarrar
   el puntero, dejar correr la animación de snap, añadir salida y validar la voz
   al arrancar. Mínimo riesgo; mantiene el panel como ventana normal.
2. **Panel integrado en el layer-shell.** Una sola superficie con
   `keyboard_interactivity` bajo demanda. Más robusto para foco y clics, pero
   mucho más cambio y riesgo en Wayland para tres bugs.
3. **Controlador de sesión nuevo.** Centralizar ciclo de vida, errores y
   entrada en una clase nueva. Orden a largo plazo, pero excesivo ahora.

## Decisiones de implementación

- **Clic vs arrastre:** subir el umbral de 4 a 10 px de distancia Manhattan
  entre pulsación y movimiento. Con 6 px ya se disparaba el arrastre y el panel
  nunca se abría (verificado con `diag_interaccion.py`).
- **Puntero:** usar `gtk_grab_add` sobre el `DrawingArea` al pulsar y
  `gtk_grab_remove` al soltar, para que no se pierdan `motion-notify` ni
  `button-release` fuera del avatar.
- **Snap:** `Mediator.on_drag_end` deja de llamar a `view.snap_to()`. Ese
  llamado ponía `_snap_to = None` y aplicaba la zona al instante, cancelando la
  animación que `engine.end_drag()` acababa de iniciar. `AvatarView.render`
  aplica la zona definitiva cuando `snap_progress` llega a 1. El método
  `snap_to` permanece en el protocolo por compatibilidad.
- **Salida:** `InputPanel` recibe un callback `on_quit` opcional, lo enlaza a un
  botón «Salir» y a un `Gtk.AccelGroup` con `<Control>q`. `main.build` pasa
  `Gtk.main_quit`, que es el dueño real de terminar el main loop.
- **Voz:** `main.build` comprueba con `shutil.which` los comandos de captura,
  STT, TTS y reproducción. Si falta alguno (o `enabled = false`), el panel
  recibe `voice_enabled=False` y se muestra un globo corto de aviso. El error
  de una transcripción se convierte en globo «No pude escuchar» en vez de morir
  en el hilo de fondo.
- El aviso de voz se muestra al arrancar; el usuario puede configurar otros
  comandos en `config.toml` y volver a abrir la aplicación.

## Lo que queda al constructor

- Elegir la forma exacta de invocar el grab en PyGObject (`Gtk.grab_add` o
  método equivalente) y comprobar que no rompe los eventos sintéticos.
- Redactar el texto concreto del globo de aviso.
- Orden de commits y verificación final quedan a su criterio, con TDD.

## Verificación

- Tests nuevos: clic con temblor abre el panel; arrastre con el puntero fuera
  mantiene el grab; `on_drag_end` no cancela el snap; botón y Ctrl+Q llaman a
  `on_quit`; voz con binarios ausentes oculta el micrófono y avisa.
- Suite completa en verde y smoke de extremo a extremo con el CLI falso.
- Repetir el diagnóstico de interacción: el temblor ya no debe producir
  `drag_start`, y al soltar debe quedar una animación de snap pendiente.

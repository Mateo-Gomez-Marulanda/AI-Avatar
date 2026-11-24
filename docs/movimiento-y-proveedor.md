# Diseño corto: movimiento del avatar y proveedor OpenCode

> Nota histórica: describe la decisión original. El contrato y la configuración vigentes son `actions.py`, el historial explícito y `README.md`; ya no existen `session_mode`, `session_flag`, `session_id_regex` ni `prompt_template`.

## Intención

Corregir que el avatar parpadee y no cambie de posición correctamente al
arrastrarlo, y cambiar el CLI por defecto de Claude a OpenCode. Es una
corrección pequeña, no un rediseño.

## Objetivos

- Que las coordenadas escritas durante el arrastre y el snap sean respetadas por
  el compositor: anclar los bordes cuyos márgenes se están usando.
- Que el snap termine anclado en la zona elegida, sin saltos ni parpadeos.
- Que `config.toml.example` use `opencode run` en lugar de `claude -p`.

## No objetivos

- Rehacer `domain/geometry.py` ni el cálculo de zonas.
- Cambiar el contrato `ESTADO`/`ABRIR`, las animaciones base ni la voz.
- Instalar o configurar modelos de OpenCode; solo cambiar el comando del CLI.
- Añadir extracción del id de sesión de OpenCode.

## Restricciones

- En Wayland un margen de GtkLayerShell solo se aplica al borde anclado.
- Los widgets y la posición viven solo en `alive/ui/`; `domain/` sigue siendo
  Python puro.
- Cada cambio se escribe primero como test que falla.

## Enfoques considerados

1. **Anclar TOP+LEFT en `_place_free` (elegido)**. `set_anchor(TOP, True)` y
   `set_anchor(LEFT, True)` antes de escribir `margin TOP=y` y `margin LEFT=x`;
   BOTTOM y RIGHT quedan sin anclar. `_apply_zone` sigue decidiendo el anclaje
   final de cada zona. Cambio mínimo y cubierto por un test de anclajes.
2. **Posicionar según el borde de cada zona**. Calcular márgenes relativos
   también para zonas ancladas a derecha/abajo. Más exacto en esos casos, pero
   modifica más código de geometría y vista para un síntoma que ya se corrige
   con el enfoque 1.
3. **`window.move()`**. Descartado: no funciona en Wayland.

Para el proveedor: `opencode run` admite `--session`/`--continue`, pero extraer
el id de su salida es frágil. Se elige `session_mode = "oneshot"`: el
historial viaja en el prompt en cada llamada y no hay que parsear ids.

## Decisiones de implementación

- En `AvatarView._place_free`: anclar TOP y LEFT, desanclar BOTTOM y RIGHT, y
  escribir los márgenes TOP e LEFT con las coordenadas objetivo. No tocar
  `_apply_zone` ni `render`.
- Test nuevo en `tests/test_avatar_view.py`: durante el arrastre y a mitad del
  snap, `get_anchor(TOP)` y `get_anchor(LEFT)` son `True` y los márgenes
  guardados son las coordenadas calculadas; al terminar el snap se aplica la
  zona.
- En `config.toml.example`: `command = ["opencode", "run"]`,
  `session_mode = "oneshot"`, `session_flag = ""`, `session_id_regex = ""`.
  `prompt_template` no cambia.
- El README ya documenta tanto OpenCode como el contrato; se ajustará solo si
  el texto dice que el ejemplo usa Claude.

## Verificación

- Test nuevo en rojo→verde y suite completa en verde.
- Repetir el diagnóstico local de posiciones (fuera del repo): durante el
  arrastre y el snap debe mostrar TOP y LEFT anclados con los márgenes
  esperados. Los márgenes que queden en bordes desanclados son inofensivos:
  layer-shell los ignora.
- Comprobar con `opencode run` real que la cabecera `> agente · modelo` no
  aparece en el globo y que las citas markdown de las respuestas se conservan.
- Smoke de extremo a extremo con el CLI falso para comprobar que el cambio de
  proveedor no rompe el flujo de respuestas.

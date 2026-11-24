# Diseño: cierre de P0 — verificación, privacidad y salida

Estado: **aprobado y ejecutado**.
Fecha: 2026-11-24.

Decisiones del usuario ya tomadas: alcance «doc + cambios de config»,
`share_output_with_model = false` por defecto, resumen de comando solo en el
panel, y verificación con entorno real.

## 1. Intención

Cerrar los apartados 11–13 de `docs/p0-asistente-conversacional.md`: ejecutar
lo que se pueda verificar en este equipo, registrar lo que queda bloqueado y
aplicar las dos decisiones que cambian comportamiento (privacidad y salida).
No es un rediseño: P0 ya está implementado y en verde.

## 2. Cambios propuestos

### 2.1 Privacidad por defecto (§12)

- `alive/domain/config.py`: `CommandConfig.share_output_with_model` de `True` a
  `False`.
- `config.toml.example`: `share_output_with_model = false`, con comentario que
  explique que la salida deja de viajar al proveedor y que el turno termina sin
  segunda llamada al modelo.
- El mediador ya tiene la rama `false` (no guarda salida en el historial y no
  vuelve a llamar al modelo); no se toca esa lógica.
- Esto **sustituye** la decisión «privacidad por comodidad» de §12.1. Se registra
  en el documento de cierre.

### 2.2 Resumen de comando solo en el panel (§13)

- `Mediator._on_command_result`: quitar `view.show_bubble(resumen, …)` de las
  dos rutas (`share_output` true y false).
- Ruta sin compartir (nuevo default): `engine.idle(now)` y
  `self._finish_turn(resumen)`. `set_busy(False, resumen)` rehabilita la entrada
  y deja el texto visible en el panel hasta el siguiente turno; no hay globo ni
  voz para el resumen.
- Ruta compartiendo: no mostrar el resumen en globo; el turno sigue con
  `pensando` y el modelo explica el resultado en el globo como hoy.
- TDD: tests rojos que exijan que el resumen no llame a `show_bubble` y que sí
  llegue al `on_status`; luego implementación mínima.

### 2.3 Registro de cierre

- `docs/p0-cierre.md`: tabla de los 14 puntos de verificación con evidencia y
  estado, decisiones de §13 cerradas, riesgos de §12 con su mitigación actual y
  límites por defecto confirmados sin cambios.

## 3. Verificación real (§11)

Entorno detectado ahora:

| Recurso | Estado |
| --- | --- |
| Sesión | `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-1`, X `:1` accesible (`xdpyinfo`) |
| OpenCode | `v2.3.2` instalado; `opencode auth list` → **No authenticated integrations** |
| Agente `alive` | Copiado a `~/.config/opencode/agents/alive.md` (2026-11-24); el smoke con `--agent alive` resolvió sin «Agent not found». |
| `playerctl` | `brave.instance3016`, `plasma-browser-integration` |
| Voz | `ffmpeg` y `paplay` presentes; faltan `whisper-cli` y `piper` |

Plan de ejecución:

1. Copiar el agente a `~/.config/opencode/agents/` (paso 11 del propio P0) y
   comprobar que el CLI lo encuentra. Es el único cambio fuera del repo.
2. Ejecutar los puntos que no dependen de modelo: arranque de la app en Wayland,
   foco del diálogo, `playerctl`, y comprobación de error claro sin agente
   (antes de copiarlo) y sin autenticación.
3. El smoke real con modelo se ejecutó el 2026-11-24 y falló con
   `provider.free-limit` (HTTP 429, «Free usage limit reached»); se registró el
   resultado literal y no se instala nada. No bloquea el cierre.
4. La verificación de voz queda bloqueada por `whisper-cli`/`piper`; no se
   instalan motores ni modelos.

## 4. Límites por defecto (§13)

No hay evidencia en uso real de que sean incómodos; se mantienen y se
documentan: proveedor 90 s, comandos 30 s / 8192 B / 3 por turno, aprobación
120 s, historial 6000 chars, globo 45 ms/char, snap 250 ms.

## 5. Verificación y entrega

- TDD rojo → verde para 2.1 y 2.2; `.venv/bin/python -m pytest -q` en verde.
- Commit local; **sin push** salvo petición explícita.
- `docs/p0-cierre.md` queda como registro final con estado real de cada punto.

## 6. Fuera de alcance

Instalar motores de voz, conectar un proveedor de OpenCode, cambiar los textos
ya implementados del prompt y del diálogo, y sustituir el arte placeholder.

# Cierre de P0 — Alive

**Fecha:** 2026-11-24
**Rama:** `main` · **Base:** `997543e` (HEAD al iniciar la Task 3).

Registro final del P0 con la verificación real ejecutada en este equipo y las
decisiones tomadas durante la revisión. Complementa a `docs/p0-asistente-conversacional.md`
(§11–§13) y a `docs/f5-cierre.md` (F5).

## 1. Verificación real ejecutada (Task 3)

### 1.1 Entorno detectado

| Verificación | Resultado literal |
| --- | --- |
| `echo $XDG_SESSION_TYPE` | `wayland` |
| `echo $WAYLAND_DISPLAY` | `wayland-1` |
| `echo $XDG_RUNTIME_DIR` | `/run/user/1000` |
| `xdpyinfo \| head -5` | `name of display: :1`, `version number: 11.0`, `vendor string: The X.Org Foundation`, `vendor release number: 12401015`, `X.Org version: 24.1.15`; exit 0. X `:1` accesible. |
| `opencode --version` | `opencode v2.3.2` |
| `opencode auth list` | `No authenticated integrations` (exit 0) |
| `opencode agent list` | **El subcomando no existe** en `opencode v2.3.2`: la salida es la ayuda de `opencode` y termina con exit 0. Se usó `opencode --help` para documentar el hallazgo; la lista de `SUBCOMMANDS` no incluye `agent`. |
| `playerctl -l` | `brave.instance3016` y `plasma-browser-integration` |
| `for b in opencode playerctl ffmpeg whisper-cli piper paplay; do command -v "$b" \|\| echo "$b NO"; done` | `/usr/bin/opencode`, `/usr/bin/playerctl`, `/usr/bin/ffmpeg`, `/usr/bin/paplay`; `whisper-cli NO`, `piper NO` |

### 1.2 Smoke real con modelo (Task 3, paso 3)

```bash
timeout 30 opencode run --format json --agent alive --archived "di solo hola" 2>&1 | head -20
```

Salida literal registrada:

```
{"type":"step_start","timestamp":1795544556239,"sessionID":"ses_df1345e74ffeSQgAfsdDJE6Jdu","part":{"id":"prt_20ecba2cf001QNQOLppL2NIqYD","sessionID":"ses_df1345e74ffeSQgAfsdDJE6Jdu","messageID":"msg_20ecba21200126L0o6s4Tv5php","type":"step-start","snapshot":"cdfd0955e4c40998551702f6d26597c74e36def2"}}
{"type":"error","timestamp":1795544556315,"sessionID":"ses_df1345e74ffeSQgAfsdDJE6Jdu","error":{"type":"provider.free-limit","message":"Free usage limit reached. Connect a provider or subscribe to OpenCode Go to keep going, or switch models.","status":429,"response":{"body":"{\"type\":\"error\",\"error\":{\"type\":\"FreeUsageLimitError\",\"message\":\"Free usage limit reached. Free models work in OpenCode (https://opencode.ai); subscribe to OpenCode Go to keep going: https://opencode.ai/go\"}}"},"retryAfterMs":20244000}}
```

Exit code: `1`.

Resultado: **fallo real registrado literalmente**. El error es de tipo
`provider.free-limit` (HTTP `429`, error `FreeUsageLimitError`). Según el propio
proveedor, se traduce al mensaje «OpenCode alcanzó el límite gratuito; conecta un
proveedor o cambia de modelo». No fue un error de agente («Agent not found»):
el agente `--agent alive` sí se resolvió.

Lazo cerrado: la salida de `opencode auth list` («No authenticated
integrations») es una observación independiente y **no** la causa del fallo del
smoke; la causa real fue el límite gratuito (`provider.free-limit`, HTTP 429).

### 1.3 Agente `alive`

Copia ejecutada (único cambio fuera del repo, aprobado por el usuario):

```bash
mkdir -p ~/.config/opencode/agents
cp .opencode/agents/alive.md ~/.config/opencode/agents/alive.md
```

`cp` terminó sin error; el archivo existe en `~/.config/opencode/agents/alive.md`.
El smoke con `--agent alive` resolvió el agente sin error de «Agent not found».

## 2. Tabla de los 14 puntos de verificación (§11)

| # | Punto (§11) | Estado real | Evidencia |
| --- | --- | --- | --- |
| 1 | Conversación de dos turnos: la segunda pregunta conserva la primera. | ⛔ No verificado en vivo | Sin verificación con modelo: el smoke falló con `provider.free-limit` (HTTP 429, ver §1.2); cubierto por tests de dominio (`tests/test_conversation.py`). |
| 2 | «Pensando…» visible mientras se espera al modelo. | ⛔ No verificado en vivo | Estado `pensando` cubierto en tests de mediador; UI en vivo no ejecutada. |
| 3 | «Abre firefox» abre directo, sin diálogo. | ⛔ No verificado en vivo | Cubierto por tests de acciones/apps (`test_mediator.py`, `test_apps.py`). |
| 4 | Sin acciones, idle alterna `sentado`/`parado` cada 20 s. | ✅ Verificado | `tests/test_animation.py`. |
| 5 | Spotify (o reproductor) → avatar `musica`; pausar/cerrar → idle. | ⛔ No verificado en vivo | `playerctl -l` lista `brave.instance3016` y `plasma-browser-integration`; reproducción real no comprobada. Tests `test_music.py`. |
| 6 | «Ejecuta `printf hola`»: diálogo con comando, qué hace y por qué; Cancelar no ejecuta; Ejecutar muestra resultado. | ✅ Verificado | Tests de diálogo/mediador + smoke con CLI falso (`tests/test_approval_dialog.py`, `tests/test_smoke_flow.py`). |
| 7 | Comando con código de salida distinto de cero: el modelo recibe el error. | ✅ Verificado | Tests de ejecución (`tests/test_commands.py`). |
| 8 | Timeout de aprobación: se cancela solo. | ✅ Verificado | Tests de mediador (`test_mediator.py`). |
| 9 | OpenCode sin autenticación o con límite: globo de error claro, sin bloqueo. | 🔶 Ejecutado con fallo real | Smoke real: exit 1 + `provider.free-limit`. Se verificó el error del proveedor, no el render del globo en vivo. |
| 10 | Segundo mensaje mientras se piensa: no se lanza otra llamada. | ✅ Verificado | Tests de mediador (`test_mediator.py`). |
| 11 | `config.toml` sin agente `alive`: error claro, no se ejecuta nada. | ⛔ No verificado en vivo | Previamente previsto en diseño; no se ejecutó en vivo. |
| 12 | Smoke con CLI falso de extremo a extremo. | ✅ Verificado | `tests/test_smoke_flow.py` (CLI falso + approver/executor falsos). |
| 13 | Smoke real con OpenCode. | 🔶 Falló por límite gratuito | Ver §1.2; no se instala nada y no bloquea el cierre. |
| 14 | `pytest -q` en verde. | ✅ Verificado | 187 passed, 2 warnings GTK. |

## 3. Decisión de privacidad

- **Decisión cerrada:** `share_output_with_model = false` (default en
  `alive/domain/config.py`, `false` con comentario mandatorio en
  `config.toml.example`).
- **Sustituye** la decisión «privacidad por comodidad» de §12.1 de
  `docs/p0-asistente-conversacional.md`.
- El mediador ya tenía la rama `false` (no guarda la salida en el historial ni vuelve
  a llamar al modelo); no se tocó esa lógica en esta tarea.

## 4. Resumen de comando: solo en panel

- Tras Task 2 (commit `997543e`), el resumen de comandos ya no se muestra en el globo
  en ninguna ruta; en la ruta por defecto (`share_output_with_model = false`) llega al
  panel vía `on_status` y se rehabilita la entrada con `busy=False`.
- No se cambió nada en esta tarea.

## 5. Límites por defecto (§13)

Sin cambios en esta tarea. Se mantienen: proveedor 90 s, comandos 30 s /
`max_output_bytes` 8192 B / 3 por turno, aprobación 120 s, historial 6000 chars,
globo 45 ms/char, snap 250 ms.

## 6. Riesgos de §12 con mitigación

| Riesgo (§12) | Mitigación actual |
| --- | --- |
| OpenCode sin proveedor autenticado | Error claro capturado; smoke real falló con `provider.free-limit`; requiere conectar un proveedor. |
| El agente `alive` debe existir | Copia global a `~/.config/opencode/agents/alive.md` ejecutada; el smoke resolvió el agente sin «Agent not found». |
| Comandos con privilegios | La aprobación es la única barrera; diálogo muestra comando exacto. |
| Salida enviada al modelo | Decisión cerrada `false`: la salida no viaja al proveedor. |
| Comandos interactivos | Sin TTY: `sudo` y similares pueden fallar; se avisa en el diálogo. |
| Foco del diálogo en Wayland | Ventana normal; si el compositor no la enfoca, el usuario puede hacer clic. No verificado en vivo. |
| El modelo puede mentir en «qué hace / por qué» | El diálogo avisa de que la explicación es del modelo. |
| Formato del modelo | Fallo seguro: si no respeta el bloque, no se ejecuta nada. |
| Música depende de MPRIS | `playerctl` presente y lista reproductores; solo `Playing` activa. |

## 7. Bloqueos del cierre (tres)

1. **OpenCode sin modelo verificable:** dos hechos separados:
   - (a) Observación de autenticación: `opencode auth list` → «No authenticated
      integrations». Es una observación previa, independiente del smoke.
   - (b) Causa real del fallo del smoke: error `provider.free-limit` (HTTP 429,
      `FreeUsageLimitError`, «Free usage limit reached»). El smoke real falló por
      el límite gratuito del modelo, no por falta de autenticación.
   Ambos impiden la verificación con modelo real; el fallo del smoke se registró
   literalmente (§1.2) y no se instala proveedor ni modelo.
2. **Voz sin binarios:** `ffmpeg` y `paplay` presentes; faltan `whisper-cli` y
   `piper`. Bloqueo previsto; no se instalan motores.
3. **Arte placeholder:** el avatar sigue siendo el placeholder vectorial hasta que
   el usuario lo aporte. Queda en P1/P2.

## 8. Resultado de la suite final

```bash
.venv/bin/python -m pytest -q
```

Salida literal (resumen):

```
........................................................................ [ 38%]
........................................................................ [ 77%]
...........................................                              [100%]
=============================== warnings summary ===============================
tests/test_avatar_view.py::test_small_jitter_is_a_click
  /home/mateo/Documentos/Alive/alive/ui/avatar_view.py:87: DeprecationWarning: GtkLayerShell.set_keyboard_interactivity is deprecated
    GtkLayerShell.set_keyboard_interactivity(self.window, False)

tests/test_avatar_view.py::test_small_jitter_is_a_click
  /home/mateo/Documentos/Alive/alive/ui/avatar_view.py:99: DeprecationWarning: Gtk.Widget.set_margin_left is deprecated
    self.bubble.set_margin_left(_BUBBLE[0])

-- Docs: https://docs.pytest.org/en/stable/how-to/coverage.html
187 passed, 2 warnings in 1.48s
```

**187 passed, 2 warnings GTK preexistentes** (mismas que la línea base tras las
Tareas 1 y 2).

## 9. Cierre

- Decisiones aplicadas: privacidad `false` (§3), resumen solo en panel (§4).
- Límites por defecto: sin cambios (§5).
- Riesgos: registrados con mitigación (§6).
- Bloqueos: los tres (§7).
- Cambios de documentación: `docs/p0-cierre.md` (nuevo), `docs/p0-cierre-design.md`
  (estado actualizado).
- Commit local sin push: `docs: cerrar P0 con verificacion real y decisiones`.

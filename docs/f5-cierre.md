# Cierre de F5 — apps y pulido

Estado: **cerrado** (2026-11-24). Criterio del `plan-de-desarrollo.md`: whitelist, apertura, manejo de errores, tests del intermediario, documentación de configuración y de cómo cambiar de proveedor.

## Cobertura verificada

| Criterio | Evidencia | Estado |
| --- | --- | --- |
| Whitelist | `[apps]` en `config.toml.example` y `alive/domain/config.py`; `AppLauncher` (`alive/application/apps.py`) divide con `shlex.split`, nunca pasa por shell. Tests: `test_apps.py`, `test_config.py`, `test_prompt.py`. | Cubierto |
| Apertura sin aprobación | `Mediator._do_app` con `AppLauncher` cableado en `alive/main.py`; alias desconocido no ejecuta nada. Tests: `test_mediator.py::test_app_action_opens_without_approval`, `::test_unknown_app_is_not_opened`. | Cubierto |
| Comandos con aprobación | Diálogo con comando exacto, qué hace y por qué; denegar, cerrar o vencer el timeout no ejecuta. Tests: `test_mediator.py`, `test_approval_dialog.py`, `test_commands.py`. | Cubierto (P0) |
| Errores visibles | Errores de proveedor, parseo, ejecución, transcripción y TTS con globo/estado y sin turnos colgados. | Cubierto (P0 + F4) |
| Tests del intermediario | 32 tests en `tests/test_mediator.py`, más smoke determinista y smoke de voz real con CLI falso en `tests/test_smoke_flow.py`. | Cubierto |
| Documentación de configuración | README: sección «Configuración», `config.toml.example` y apartado «Para añadir cosas» con proveedor, app, zona, acción y gesto nuevos. | Cubierto |
| Cambiar de proveedor | README describe el módulo en `alive/infrastructure/providers/` y el protocolo en `alive/domain/contracts.py`; el ejemplo usa OpenCode con agente `alive`. Anti-herramientas documentado. | Cubierto |

Verificación: `.venv/bin/python -m pytest -q` → **183 passed, 2 warnings GTK preexistentes**. Sin cambios de código en este cierre.

## Ajustes de documentación aplicados

- Los estados de `plan-de-desarrollo.md`, `docs/p0-asistente-conversacional.md` y `docs/f4-voz-y-no-molestar-design.md` dejan de decir «pendiente de aprobación».
- Los documentos de decisiones antiguas llevan una nota de vigencia: describen el contrato `ESTADO`/`ABRIR`, `orders.py` y los modos de sesión que P0 sustituyó por `actions.py` e historial explícito. Se conservan como registro, no como configuración vigente.

## Queda pendiente (no bloquea el cierre)

1. **Comprobación manual de voz** con `ffmpeg`, `whisper-cli`, `piper` y `paplay`: boca sincronizada y «no molestar» en la esquina. No se instalan motores ni modelos por decisión de diseño.
2. **Smoke real con OpenCode**: requiere proveedor autenticado con cuota; la puerta determinista ya está cubierta por CLI falso.
3. **Arte definitivo**: el avatar sigue siendo el placeholder vectorial hasta que el usuario lo aporte; el contrato es `render(frame)`.

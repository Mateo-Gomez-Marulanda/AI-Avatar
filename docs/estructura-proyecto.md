# Diseño: restructura del proyecto por capas

> Nota histórica: la tabla de archivos refleja el estado de entonces. Hoy `orders.py` es `actions.py`, y el contrato `ESTADO`/`ABRIR` fue sustituido por el bloque `alive-accion`; la estructura actual está en `README.md`.

## Intención

El paquete `alive/` quedó plano después de la primera implementación. Queremos que
cada parte tenga un lugar previsible y que desaparezca el worktree que ya cumplió
su función. No queremos cambiar comportamiento: es una reorganización.

## Objetivos

- `alive/` dividido en `domain/`, `application/`, `infrastructure/` y `ui/`, con
  `main.py` como raíz de composición.
- Dependencias en una sola dirección: `ui`, `application` e `infrastructure`
  pueden importar `domain`; `domain` no importa nada de las otras capas; `main`
  importa todas para cablearlas.
- `.gitignore` cubre cualquier carpeta llamada `superpowers/`.
- Eliminar `.worktrees/` y la rama `alive-avatar`, ya fusionada en `main`.
- Suite de tests en verde y imports actualizados.

## No objetivos / antiobjetivos

- No cambiar el contrato cerrado (`ESTADO` / `ABRIR`), las animaciones, la voz ni
  la geometría.
- No renombrar módulos por capricho: solo los cambios que la capa exige.
- No guardar este diseño dentro de `docs/superpowers/`, porque esa carpeta queda
  ignorada.

## Restricciones

- GTK3/GtkLayerShell y los widgets solo en `ui/`. `main.py` es la raíz de
  composición y está autorizado a importar `Gdk`, `GLib` y `Gtk` para el bootstrap:
  obtener el monitor, registrar el tick y arrancar el main loop. El runner de
  fondo con `threading` + `GLib.idle_add` vive en `infrastructure/background.py`
  y usa GLib solo para devolver resultados al hilo principal.
- `domain/` es Python puro: ni GTK ni subprocess.
- Los tests siguen planos en `tests/`; solo cambian sus imports.

## Approaches considerados

1. **Por capas (elegido)**: cuatro carpetas con dependencias claras. Cuesta
   actualizar imports, pero deja una regla simple para ubicar archivos nuevos.
2. **Por responsabilidad**: `core/`, `services/`, `ui/`, `providers/`. Más corto,
   pero mezcla servicios de aplicación con adaptadores de infraestructura.
3. **Una carpeta por módulo**: doce carpetas con un archivo cada una. Descartado:
   más ruido que orden.

## Decisiones de implementación

Toda la restructura se aplica en el checkout principal
`/home/mateo/Documentos/Alive` (rama `main`). El worktree
`.worktrees/alive-avatar` se borra al final, después de que los cambios estén
commiteados en `main`; antes se copia su ledger a `.superpowers/` del checkout
principal.

| Capa | Archivos |
| --- | --- |
| `alive/domain/` | `config.py`, `orders.py`, `animation.py`, `geometry.py`, `contracts.py` |
| `alive/application/` | `mediator.py`, `apps.py`, `audio.py` |
| `alive/infrastructure/` | `providers/cli.py`, `background.py` |
| `alive/ui/` | `avatar_view.py`, `input_panel.py` |
| `alive/` | `main.py` (composition root), `__init__.py` |

- `interfaces.py` desaparece: `AiReply`, `ProviderError` y los protocolos
  (`AiProvider`, `CommandRunner`, `BackgroundLike`, `AvatarViewLike`, `VoiceLike`)
  pasan a `domain/contracts.py`. `AvatarViewLike` referencia `Frame` de
  `domain/animation.py`.
- `providers/base.py` desaparece: sus dos símbolos ya viven en `domain/contracts.py`
  y `infrastructure/providers/cli.py` los importa de ahí.
- `GtkBackgroundRunner` sale de `main.py` y pasa a
  `infrastructure/background.py`.
- Rutas nuevas de import, por ejemplo:
  `from alive.domain.config import Config`,
  `from alive.application.mediator import Mediator`,
  `from alive.infrastructure.providers.cli import CliProvider`,
  `from alive.ui.avatar_view import AvatarView`.
- Cada paquete lleva `__init__.py` vacío.

## Gitignore y documentación

- Añadir patrón genérico `superpowers/` a `.gitignore`, manteniendo los patrones
  específicos `.superpowers/` y `docs/superpowers/` ya presentes.
- El plan `docs/superpowers/plans/2026-11-23-alive-avatar.md` ya está versionado:
  ignorar la carpeta no lo desversiona. Se conserva.
- Este documento vive en `docs/estructura-proyecto.md` para no quedar ignorado y
  se versiona en el primer commit de la restructura.

## Limpieza

- Copiar el ledger `.worktrees/alive-avatar/.superpowers/sdd/.../progress.md` a
  `.superpowers/sdd/.../progress.md` en el repo principal antes de borrar el
  worktree.
- `git worktree remove .worktrees/alive-avatar`, `git worktree prune` y
  `git branch -d alive-avatar`.
- Como el `.venv` estaba dentro del worktree, recrearlo en la raíz con
  `python3 -m venv --system-site-packages .venv` e instalar `pytest`.
- Borrar cachés ignoradas `__pycache__` y `.pytest_cache`.

## Verificación

- `.venv/bin/python -m pytest -q`.
- Importar todos los módulos nuevos en un solo `python -c`.
- Smoke de `python -m alive.main --config config.toml.example` con el CLI falso
  usado en la verificación anterior.
- `git status` limpio salvo los cambios esperados.

## Lo que queda al constructor

- Orden de commits: se propone uno para la restructura y otro para gitignore y
  limpieza, pero el constructor puede decidir otro orden si lo ve mejor.

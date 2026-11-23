"""Ventana overlay GTK3 con layer-shell: avatar, globo, zonas y arrastre."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

import cairo
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402

from alive.domain.config import Config, Zone  # noqa: E402
from alive.domain.geometry import Rect, nearest_zone, zone_rect  # noqa: E402

_SIZE = (200, 300)
_BODY = (54, 96, 92, 132)
_HEAD = (56, 40, 88, 88)
_BUBBLE = (8, 8, 184, 56)

_STATE_COLORS = {
    "sentado": (0.36, 0.62, 0.78),
    "parado": (0.30, 0.70, 0.55),
    "escuchando": (0.95, 0.72, 0.25),
    "pensando": (0.70, 0.55, 0.90),
    "hablando": (0.95, 0.45, 0.45),
    "musica": (0.40, 0.55, 0.95),
    "arrastrado": (0.60, 0.60, 0.65),
    "no_molestar": (0.35, 0.35, 0.38),
}


class AvatarView:
    def __init__(self, config: Config, monitor: Rect) -> None:
        self.config = config
        self.monitor = monitor
        self.frame = None
        self._mouth = 0.0
        self._bubble_text = ""
        self._bubble_timeout = 0
        self._click_through = False
        self._dragging = False
        self._drag_offset = (0, 0)
        self._drag_origin: Rect | None = None
        self._snap_to: Rect | None = None
        self._zone_name = "flotante"
        self.on_drag_start = lambda: None
        self.on_drag_end = lambda zone: None
        self.on_activate_input = lambda: None

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_app_paintable(True)
        self.window.set_decorated(False)
        self.window.set_default_size(*_SIZE)
        self.window.set_size_request(*_SIZE)
        self.window.set_title("Alive avatar")

        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.window.set_visual(visual)

        css = Gtk.CssProvider()
        css.load_from_data(b".window { background: transparent; }")
        self.window.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.window.get_style_context().add_class("window")

        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_exclusive_zone(self.window, 0)
        GtkLayerShell.set_keyboard_interactivity(self.window, False)
        self._apply_zone(self._choose_initial_zone())

        self.area = Gtk.DrawingArea()
        self.area.set_app_paintable(True)
        self.area.connect("draw", self._draw)

        self.bubble = Gtk.Label(label="")
        self.bubble.set_line_wrap(True)
        self.bubble.set_max_width_chars(28)
        self.bubble.set_halign(Gtk.Align.START)
        self.bubble.set_valign(Gtk.Align.START)
        self.bubble.set_margin_left(_BUBBLE[0])
        self.bubble.set_margin_top(_BUBBLE[1])
        self.bubble.set_no_show_all(True)

        overlay = Gtk.Overlay()
        overlay.add(self.area)
        overlay.add_overlay(self.bubble)
        self.window.add(overlay)

        self.window.connect("button-press-event", self._button_press)
        self.window.connect("motion-notify-event", self._motion)
        self.window.connect("button-release-event", self._button_release)
        self.window.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.area.set_events(self.window.get_events())
        self._update_input_region()

    # -- configuración -------------------------------------------------

    def set_callbacks(self, on_drag_start, on_drag_end, on_activate_input) -> None:
        self.on_drag_start = on_drag_start
        self.on_drag_end = on_drag_end
        self.on_activate_input = on_activate_input

    def _choose_initial_zone(self) -> str:
        if "barra" in self.config.zones:
            return "barra"
        return next(iter(self.config.zones), "flotante")

    def _apply_zone(self, name: str) -> None:
        zone: Zone | None = self.config.zones.get(name)
        if zone is None:
            zone = Zone("floating", x=self.monitor.width // 3, y=self.monitor.height // 3)
        rect = zone_rect(self.monitor, zone, _SIZE)
        self._zone_name = name
        for edge in (
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.BOTTOM,
            GtkLayerShell.Edge.LEFT,
            GtkLayerShell.Edge.RIGHT,
        ):
            GtkLayerShell.set_anchor(self.window, edge, False)
        if zone.anchor in ("top", "left", "right", "bottom"):
            edge = {
                "top": GtkLayerShell.Edge.TOP,
                "left": GtkLayerShell.Edge.LEFT,
                "right": GtkLayerShell.Edge.RIGHT,
                "bottom": GtkLayerShell.Edge.BOTTOM,
            }[zone.anchor]
            GtkLayerShell.set_anchor(self.window, edge, True)
            margin = {
                "top": rect.y,
                "left": rect.x,
                "right": self.monitor.width - rect.x - rect.width,
                "bottom": self.monitor.height - rect.y - rect.height,
            }[zone.anchor]
            GtkLayerShell.set_margin(self.window, edge, max(0, margin))
        else:
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.LEFT, rect.x)
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, rect.y)

    def _place_free(self, x: int, y: int) -> None:
        """Coloca la ventana por márgenes; nunca usa window.move() en Wayland."""
        for edge in (
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.BOTTOM,
            GtkLayerShell.Edge.RIGHT,
        ):
            GtkLayerShell.set_anchor(self.window, edge, False)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.LEFT, int(x))
        GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, int(y))

    # -- eventos -------------------------------------------------------

    def _button_press(self, widget, event) -> bool:
        if event.button != 1 or self._click_through:
            return False
        self._dragging = False
        self._drag_offset = (int(event.x), int(event.y))
        self._press_point = (event.x_root, event.y_root)
        self._drag_origin = Rect(
            int(event.x_root - event.x - self.monitor.x),
            int(event.y_root - event.y - self.monitor.y),
            _SIZE[0],
            _SIZE[1],
        )
        return True

    def _motion(self, widget, event) -> bool:
        if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            return False
        if not self._dragging:
            origin = getattr(self, "_press_point", None)
            if origin is None:
                return False
            if abs(event.x_root - origin[0]) + abs(event.y_root - origin[1]) < 4:
                return False
            self._dragging = True
            self.on_drag_start()
        x = event.x_root - self.monitor.x - self._drag_offset[0]
        y = event.y_root - self.monitor.y - self._drag_offset[1]
        self._place_free(x, y)
        return True

    def _button_release(self, widget, event) -> bool:
        if event.button != 1:
            return False
        if not self._dragging:
            self.on_activate_input()
            return False
        self._dragging = False
        pointer = (int(event.x_root - self.monitor.x), int(event.y_root - self.monitor.y))
        name = nearest_zone(self.monitor, pointer, self.config.zones, _SIZE)
        zone = self.config.zones.get(name, Zone("floating"))
        self._snap_to = zone_rect(self.monitor, zone, _SIZE)
        self._zone_name = name
        self._snap_from = Rect(
            int(event.x_root - self.monitor.x - self._drag_offset[0]),
            int(event.y_root - self.monitor.y - self._drag_offset[1]),
            _SIZE[0],
            _SIZE[1],
        )
        self.on_drag_end(name)
        return True

    # -- AvatarViewLike ------------------------------------------------

    def render(self, frame) -> None:
        self.frame = frame
        self._mouth = frame.mouth
        if self._snap_to is not None:
            progress = min(1.0, max(0.0, frame.snap_progress))
            source = self._snap_from
            target = self._snap_to
            x = source.x + (target.x - source.x) * progress
            y = source.y + (target.y - source.y) * progress
            self._place_free(x, y)
            if progress >= 1.0:
                self._snap_to = None
                self._apply_zone(self._zone_name)
        self.area.queue_draw()

    def show_bubble(self, text: str, ms_per_char: int) -> None:
        self.bubble.set_text(text)
        self.bubble.show()
        self._update_input_region()
        if self._bubble_timeout:
            Gtk.source_remove(self._bubble_timeout)
        delay = max(1200, len(text) * ms_per_char)
        self._bubble_timeout = GLib.timeout_add(delay, self.hide_bubble)

    def hide_bubble(self) -> bool:
        self.bubble.hide()
        self._bubble_timeout = 0
        self._update_input_region()
        return False

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        self._update_input_region()

    def snap_to(self, zone_name: str) -> None:
        self._snap_to = None
        self._apply_zone(zone_name)

    def show_all(self) -> None:
        self.window.show_all()
        self._update_input_region()

    # -- dibujo --------------------------------------------------------

    def _update_input_region(self) -> None:
        if self._click_through:
            self.window.input_shape_combine_region(cairo.Region())
            return
        region = cairo.Region()
        for x, y, w, h in (_BODY, _HEAD):
            region.union(cairo.Region(cairo.RectangleInt(x, y, w, h)))
        if self.bubble.get_visible():
            region.union(cairo.Region(cairo.RectangleInt(*_BUBBLE)))
        self.window.input_shape_combine_region(region)

    def _draw(self, widget, context: cairo.Context) -> bool:
        state = self.frame.state if self.frame is not None else "sentado"
        color = _STATE_COLORS.get(state, _STATE_COLORS["sentado"])
        context.set_source_rgba(*color, 0.92)
        x, y, w, h = _BODY
        context.rectangle(x, y, w, h)
        context.fill()

        hx, hy, hw, hh = _HEAD
        context.set_source_rgba(*color, 1.0)
        context.arc(hx + hw / 2, hy + hh / 2, hw / 2, 0, 2 * 3.14159265)
        context.fill()

        context.set_source_rgba(0.08, 0.08, 0.12, 1.0)
        for ex in (hx + 30, hx + 58):
            context.arc(ex, hy + 38, 4, 0, 2 * 3.14159265)
            context.fill()
        mouth_h = 4 + 22 * max(0.0, min(1.0, self._mouth))
        context.arc(hx + 44, hy + 60, 9, 0.15, 2.99)
        context.fill()
        context.rectangle(hx + 35, hy + 58, 18, mouth_h)
        context.fill()
        return False

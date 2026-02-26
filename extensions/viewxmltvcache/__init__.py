# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2026 Dmitriy Yefremov <https://github.com/DYefremov>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Author: Dmitriy Yefremov
#

from gi.repository import Gtk, GLib, Gio

from app.tools.epg import EpgEvent
from app.ui.dialogs import translate, show_dialog, DialogType
from app.ui.epg.epg import EpgCache
from extensions import BaseExtension


class Viewxmltvcache(BaseExtension):
    LABEL = "View XMLTV cache."
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        app._stack_epg_box.connect("realize", self.on_epg_tab_realize)

    def on_epg_tab_realize(self, widget):
        from app.ui.epg.epg import EpgTool

        children = widget.get_children()
        if not children or not isinstance(children[0], EpgTool):
            self.log("Initialization error [EPG tab].")
            return

        self._tool = children[0]

        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON))
        menu_button.set_tooltip_text(translate("Current EPG cache contents."))
        # Menu.
        menu = Gio.Menu()
        section = Gio.Menu()
        menu.append_section(None, section)
        self.app.set_action("show_current_epg_cache", lambda a, v: self.on_cache_view())
        section.append("Show current EPG cache", "app.show_current_epg_cache")
        self.app.set_action("show_full_epg_cache", lambda a, v: self.on_cache_view(True))
        section.append("Show full EPG cache", "app.show_full_epg_cache")
        section = Gio.Menu()
        menu.append_section(None, section)
        self.app.set_action("clear_epg_name_cache", self.clear_name_cache)
        section.append("Clear EPG name cache", "app.clear_epg_name_cache")

        src_button = self._tool._src_xmltv_button
        box = src_button.get_parent().get_parent()
        menu_button.set_menu_model(menu)
        src_button.bind_property("active", menu_button, "visible")
        box.pack_end(menu_button, False, True, 0)

    def on_cache_view(self, full=False):
        cache = self._tool._epg_cache
        if not cache:
            self.app.show_error_message("Cache is missing or empty!")
            return

        if cache.is_run:
            self.app.show_error_message("Data loading in progress!")
            return

        self._tool._multi_epg_button.set_active(True)
        self.app.wait_dialog.show()

        gen = self.update_epg_data(full)
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def update_epg_data(self, full=False):
        c_gen = self._tool.clear()
        yield from c_gen

        model = self._tool._model
        label = self._tool._event_count_label
        factor = self._tool.LOAD_FACTOR // 2
        cache = self._tool._epg_cache.events

        if full:
            reader = self._tool._epg_cache._reader
            cache = {s: srv.events for s, srv in reader._cache.items()}

        import time

        current_time = time.time()

        for index, item in enumerate(cache.items()):
            s, ev = item
            start, end, length = current_time, current_time, 0
            names = None
            if full:
                names = reader._cache[s].names
                names = ",".join(names) if len(names) > 1 else None

            if len(ev) > 1:
                start, end = (ev[0].start, ev[-1].duration) if full else (ev[0].start, ev[-1].end)
                length = end - start

            desc = f"{translate('Events')} -> {len(ev)}"
            model.append(EpgEvent(s, names, start, end, length, desc, {}))
            if index % factor == 0:
                label.set_text(str(len(model)))
                yield True

        label.set_text(str(len(model)))
        self.app.wait_dialog.hide()
        yield True

    def clear_name_cache(self, action, value):
        msg = translate("All previously saved values will be removed from the cache!")
        msg = f"\n{msg}\n\n\t\t\t\t\t{translate('Are you sure?')}"

        if show_dialog(DialogType.QUESTION, transient=self.app.app_window, text=msg) != Gtk.ResponseType.OK:
            return
        EpgCache.NAME_CACHE.clear()

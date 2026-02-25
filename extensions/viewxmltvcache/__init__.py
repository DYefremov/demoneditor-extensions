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


from gi.repository import Gtk, GLib

from app.tools.epg import EpgEvent
from app.ui.dialogs import translate
from extensions import BaseExtension


class Viewxmltvcache(BaseExtension):
    LABEL = "View XMLTV cache."
    EMBEDDED = True

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

        src_button = self._tool._src_xmltv_button
        box = src_button.get_parent().get_parent()
        button = Gtk.Button.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON)
        button.set_tooltip_text(translate("Current EPG cache contents."))
        button.connect("clicked", self.on_cache_view)
        src_button.bind_property("active", button, "visible")
        box.pack_end(button, False, True, 0)

    def on_cache_view(self, button):
        cache = self._tool._epg_cache
        if not cache:
            self.app.show_error_message("Cache is missing or empty!")
            return

        if cache.is_run:
            self.app.show_error_message("Data loading in progress!")
            return

        self._tool._multi_epg_button.set_active(True)
        self.app.wait_dialog.show()

        gen = self.update_epg_data()
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def update_epg_data(self):
        c_gen = self._tool.clear()
        yield from c_gen

        cache = self._tool._epg_cache
        model = self._tool._model
        label = self._tool._event_count_label
        factor = self._tool.LOAD_FACTOR // 2

        for index, item in enumerate(cache.events.items()):
            s, ev = item
            start, end = ev[0].start, ev[-1].end
            length = end - start
            desc = f"{translate('Events')} -> {len(ev)}"
            model.append(EpgEvent(s, None, start, end, length, desc, {}))
            if index % factor == 0:
                label.set_text(str(len(model)))
                yield True

        label.set_text(str(len(model)))
        self.app.wait_dialog.hide()
        yield True

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

from gi.repository import Gdk, Gtk

from app.ui.dialogs import translate, show_dialog, DialogType
from app.ui.epg.epg import EpgCache
from app.ui.uicommons import Column
from extensions import BaseExtension


class Xmltvtonamecache(BaseExtension):
    LABEL = "XMLTV to EPG name cache"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        self._reader = None
        self._save_button = None
        self._multi_epg_button = None
        self._src_xmltv_button = None
        self._name_cache = EpgCache.NAME_CACHE

        app._stack_epg_box.connect("realize", self.on_epg_tab_realize)

    def on_epg_tab_realize(self, widget):
        from app.ui.epg.epg import EpgTool

        children = widget.get_children()
        if not children or not isinstance(children[0], EpgTool):
            self.log("Initialization error [EPG tab].")
            return

        tool = children[0]

        self._multi_epg_button = tool._multi_epg_button
        self._src_xmltv_button = tool._src_xmltv_button
        self._tool = tool

        view = tool._view
        view.enable_model_drag_dest([], Gdk.DragAction.COPY)
        view.drag_dest_add_text_targets()

        view.connect("drag-drop", self.on_epg_view_drag_drop)
        view.connect("drag-data-received", self.on_epg_view_drag_data_received)

    def on_epg_view_drag_drop(self, view, context, x, y, time):
        view.stop_emission_by_name("drag_drop")
        if not self._multi_epg_button.get_active() or not self._src_xmltv_button.get_active():
            self.app.show_error_message("Operation not allowed in this context!")
            return

        self.app.on_info_bar_close()

        targets = context.list_targets()
        view.drag_get_data(context, targets[-1] if targets else Gdk.atom_intern("text/plain", False), time)

    def on_epg_view_drag_data_received(self, view, context, x, y, data, info, time):
        view.stop_emission_by_name("drag_data_received")
        enabled = self.app.app_settings.enable_epg_name_cache
        if not enabled:
            msg = f"\n{translate('EPG name cache is disabled!')}\n\n{translate('Do you want to enable it?')}"
            if show_dialog(DialogType.QUESTION, self.app.app_window, msg) != Gtk.ResponseType.OK:
                return

            self.app.app_settings.enable_epg_name_cache = True

        txt = data.get_text()
        if not txt:
            return

        itr_str, sep, src = txt.partition(self.app.DRAG_SEP)
        if src != self.app.FAV_MODEL:
            self.app.show_error_message("Operation not allowed in this context!")
            return

        model = self.app.fav_view.get_model()
        itrs = itr_str.split(",")
        if len(itrs) > 1:
            self.app.show_error_message("Please, select only one item!")
            return

        src_name = model.get_value(model.get_iter_from_string(itrs[0]), Column.FAV_SERVICE)
        path, pos = view.get_dest_row_at_pos(x, y) or (None, None)
        if not path:
            return

        id_name = view.get_model()[path][Column.EPG_SERVICE]

        if not self._reader:
            self._reader = self._tool._epg_cache.current_reader

        if self._reader and id_name in self._reader.cache:
            self._name_cache[src_name] = id_name
            self.app.emit("epg-cache-initialized", self._name_cache)
            self._save_button.set_sensitive(True) if self._save_button else self.init_save_button()
        else:
            msg = f"{translate('Operation not allowed in this context!')} {translate('Full XMLTV cache not loaded!')}"
            self.app.show_error_message(msg)

        context.finish(True, False, time)

    def init_save_button(self):
        box = self._src_xmltv_button.get_parent().get_parent()
        self._save_button = Gtk.Button.new_from_icon_name("document-save-symbolic", Gtk.IconSize.BUTTON)
        self._save_button.set_tooltip_text(translate("Save to EPG name cache."))
        self._save_button.set_visible(True)
        self._save_button.set_sensitive(True)
        self._save_button.connect("clicked", self.on_cache_save)
        self._src_xmltv_button.bind_property("active", self._save_button, "visible")
        box.pack_end(self._save_button, False, True, 0)

    def on_cache_save(self, button):
        if show_dialog(DialogType.QUESTION, self.app.app_window, translate('Are you sure?')) == Gtk.ResponseType.OK:
            EpgCache.update_name_cache(self.app.app_settings.default_data_path, self._name_cache)
            button.set_sensitive(False)

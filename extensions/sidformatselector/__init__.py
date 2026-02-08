# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2026 Dmitriy Yefremov
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

import os

from gi.repository import Gdk, Gtk

from app.ui.uicommons import Column
from extensions import BaseExtension


class Sidformatselector(BaseExtension):
    LABEL = "SID format selector"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        column = app.services_view.get_column(7)
        cells = column.get_cells()
        if not cells:
            self.log("Init error.")
            return

        renderer = cells[0]
        column.set_cell_data_func(renderer, self.sid_data_func)
        button = column.get_button()
        button.connect("button-press-event", self.on_button_press)

        self._is_dec = False
        _base_path = os.path.dirname(__file__)
        builder = Gtk.Builder.new_from_file(f"{_base_path}{os.sep}menu.ui")
        self._menu = builder.get_object("menu")
        self._dec_menu_item = builder.get_object("dec_item")
        self._dec_menu_item.connect("toggled", self.on_dec_toggled)

    def sid_data_func(self, column, renderer, model, itr, data):
        if self._is_dec:
            renderer.set_property("text", f"{int(model.get_value(itr, Column.SRV_SSID), 16)}")
        return True

    def on_button_press(self, button, event):
        if event.get_event_type() == Gdk.EventType.BUTTON_PRESS and event.button == Gdk.BUTTON_SECONDARY:
            self._menu.popup_at_pointer()
            return True
        return False

    def on_dec_toggled(self, item):
        self._is_dec = item.get_active()


if __name__ == "__main__":
    pass

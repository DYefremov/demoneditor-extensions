# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2023 Dmitriy Yefremov
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

import re

from gi.repository import Gtk

from app.ui.uicommons import Column
from extensions import BaseExtension


class Filterhighlight(BaseExtension):
    LABEL = "Filter highlight"
    EMBEDDED = True

    def __init__(self, app):
        super().__init__(app)

        style_context = self.app.services_view.get_style_context()
        self._color = style_context.get_color(Gtk.StateFlags.LINK).to_color().to_string()

        app._stack_services_frame.connect("realize", self.on_bq_tab_realize)
        app._stack_epg_box.connect("realize", self.on_epg_tab_realize)

    def on_bq_tab_realize(self, widget):
        # Sat
        sat_entry = self.app._filter_entry
        view = self.app.services_view
        self.init_data_func(view, 2, sat_entry, Column.SRV_SERVICE, 1)  # Service
        self.init_data_func(view, 3, sat_entry, Column.SRV_PACKAGE, 0)  # Package
        # IPTV
        iptv_entry = self.app._iptv_filter_entry
        view = self.app.iptv_services_view
        self.init_data_func(view, 0, iptv_entry, Column.IPTV_SERVICE, 0)  # Service

    def on_epg_tab_realize(self, widget):
        from app.ui.epg.epg import EpgTool

        children = widget.get_children()
        if not children or not isinstance(children[0], EpgTool):
            self.log("Initialization error [EPG tab].")
            return

        tool = children[0]
        view = tool._view
        entry = tool._filter_entry
        self.init_data_func(view, 0, entry, 0, 0)  # Service
        self.init_data_func(view, 1, entry, 1, 0)  # Title
        self.init_data_func(view, 5, entry, 5, 0)  # Description

    def init_data_func(self, view, column, entry, m_index, cel):
        v_column = view.get_column(column)
        v_column.set_cell_data_func(v_column.get_cells()[cel], lambda c, r, m, i, d: self.data_func(
            m_index, r, m, i, entry.get_text().upper()))

    def data_func(self, column, renderer, model, itr, f_txt):
        txt = model[itr][column]
        if f_txt and f_txt in txt.upper():
            murk = re.sub(re.escape(f_txt),
                          lambda m:
                          f'<span foreground="{self._color}"><b>{m.group()}</b></span>',
                          txt, flags=re.I)
            renderer.set_property("markup", murk)


if __name__ == "__main__":
    pass

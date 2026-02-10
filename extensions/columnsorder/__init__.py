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


from app.commons import run_idle
from app.ui.uicommons import Page
from extensions import BaseExtension


class Columnsorder(BaseExtension):
    LABEL = "Columns order"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        self._initialized = set()
        self.update_view_state(app.fav_view)
        app.connect("page-changed", self.on_page_changed)

    @run_idle
    def update_view_state(self, view):
        view.set_reorderable(True)
        [column.set_reorderable(True) for column in filter(lambda c: c.get_visible(), view.get_columns())]

    def on_page_changed(self, app, page):
        if page in self._initialized:
            return

        self._initialized.add(page)

        if page is Page.SERVICES:
            self.update_view_state(app.services_view)
            self.update_view_state(app.iptv_services_view)
        elif page is Page.SATELLITE:
            self.update_view_state(app._satellite_tool._satellite_view)
            self.update_view_state(app._satellite_tool._sat_tr_view)
            self.update_view_state(app._satellite_tool._ter_tr_view)
            self.update_view_state(app._satellite_tool._cable_tr_view)
        elif page is page.PICONS:
            self.update_view_state(app._picon_manager._picons_src_view)
            self.update_view_state(app._picon_manager._picons_dest_view)
        elif page is Page.EPG:
            self.update_view_state(app._epg_tool._view)
        elif page is Page.TIMERS:
            self.update_view_state(app._timers_tool._view)
        elif page is Page.RECORDINGS:
            self.update_view_state(app._recordings_tool._rec_view)


if __name__ == "__main__":
    pass

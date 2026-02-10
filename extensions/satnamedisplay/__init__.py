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


import os.path
import xml.etree.ElementTree as ETree

from gi.repository import GLib

from app.eparser.satxml import get_pos_str
from app.ui.dialogs import translate
from app.ui.uicommons import Column
from extensions import BaseExtension


class Satnamedisplay(BaseExtension):
    LABEL = "Satellite name display"
    EMBEDDED = True
    VERSION = "1.1"

    def __init__(self, app):
        super().__init__(app)

        column = app.services_view.get_column(13)
        cells = column.get_cells()
        if not cells:
            self.log("Init error.")
            return

        self._satellites = {}
        self._is_update = False

        column.set_title(f"{translate('Pos')} [{translate('Satellite')}]")
        renderer = cells[0]
        column.set_cell_data_func(renderer, self.sat_name_data_func)
        app.connect("profile-changed", self.on_profile_changed)

        gen = self.update_satellite_names(app.app_settings.profile_data_path)
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def sat_name_data_func(self, column, renderer, model, itr, data):
        pos = model.get_value(itr, Column.SRV_POS)
        name = self._satellites.get(pos)
        if name:
            renderer.set_property("text", name)
        return True

    def on_profile_changed(self, app, prf):
        gen = self.update_satellite_names(app.app_settings.profile_data_path)
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def update_satellite_names(self, data_path):
        if self._is_update:
            self.log("Error. Update in progress...")
            return

        sat_file = os.path.join(data_path, "satellites.xml")
        if not os.path.isfile(sat_file):
            return

        self._satellites.clear()
        for e in ETree.parse(sat_file).iter("sat"):
            pos, name = e.get("position", None),  e.get("name", None)
            if pos and name:
                self._satellites[get_pos_str(int(pos))] = name
            yield True

        yield True


if __name__ == "__main__":
    pass

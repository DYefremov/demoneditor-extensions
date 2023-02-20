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

import os
import re

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from extensions import BaseExtension


class Streamimport(BaseExtension):
    LABEL = "Advanced streams import"

    def exec(self):
        dialog = ImportDialog(self.app)
        dialog.show()


class ImportDialog(Gtk.Window):
    PARAMS = re.compile(r'(\S+)="(.*?)"')

    def __init__(self, app, **kwargs):
        super().__init__(title=Streamimport.LABEL,
                         destroy_with_parent=True,
                         default_width=560,
                         icon_name="demon-editor",
                         modal=True, **kwargs)

        self._app = app

        _base_path = os.path.dirname(__file__)
        builder = Gtk.Builder.new_from_file(f"{_base_path}{os.sep}dialog.ui")
        self.add(builder.get_object("main_box"))
        self._model = builder.get_object("model")

        self._chooser_button = builder.get_object("file_chooser_button")
        self._chooser_button.connect("file-set", self.on_file_set)
        self._input_text_view = builder.get_object("input_text_view")
        self._input_text_view.connect("paste-clipboard", self.on_paste_clipboard)

    def on_file_set(self, button):
        self._model.clear()
        path = button.get_filename()
        if not os.path.isfile(path):
            return

        gen = self.update_from_file(path)
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def on_paste_clipboard(self, view: Gtk.TextView):
        pass

    def update_from_file(self, path):
        self._chooser_button.set_sensitive(False)

        with open(path, "rb") as file:
            data = file.read()
            encoding = "utf-8"

            try:
                import chardet
            except ModuleNotFoundError:
                pass
            else:
                enc = chardet.detect(data)
                encoding = enc.get("encoding", "utf-8")

            yield from self.process_data(str(data, encoding=encoding, errors="ignore").splitlines())

            yield self._chooser_button.set_sensitive(True)

    def process_data(self, lines):
        group = None
        name = None
        logo = None
        ch_id = None

        for line in lines:
            if line.startswith("#EXTM3U"):
                params = dict(self.PARAMS.findall(line))
                epg_src = params.get("x-tvg-url", params.get("url-tvg", None))
                epg_src = epg_src.split(",") if epg_src else None
            elif line.startswith("#EXTINF"):
                params = dict(self.PARAMS.findall(line))
                group = params.get("group-title", None)
                name = params.get("tvg-name", None)
                logo = params.get("tvg-logo", None)
                ch_id = params.get("tvg-id", None)
            elif line.startswith("#EXTGRP"):
                group = line.strip("#EXTGRP:").strip()
            elif not line.startswith("#") and "://" in line:
                url = line.strip()
                if name:
                    name = name.strip()
                else:
                    pass

                ch_id = ch_id.strip() if ch_id else ch_id
                logo = logo.strip() if logo else logo
                yield self._model.append((None, name, group, True, ch_id, url, logo, None))


if __name__ == "__main__":
    pass

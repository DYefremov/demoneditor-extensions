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


from collections import defaultdict

from gi.repository import Gtk, GLib

from app.ui.dialogs import get_message
from app.ui.main_helper import get_iptv_data
from app.ui.uicommons import Column
from extensions import BaseExtension


class Iptvcleanup(BaseExtension):
    LABEL = "IPTV bouquets cleanup"

    class CleanupDialog(Gtk.Dialog):
        def __init__(self, data: dict, **kwargs):
            super().__init__(title="IPTV bouquets cleanup", default_width=320, **kwargs)

            area = self.get_content_area()
            label = Gtk.Label(margin_top=15, margin_bottom=15)
            count = 0

            if not data.keys():
                self.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
            else:
                count = sum((len(x) for x in data.values()))
                self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_DELETE, Gtk.ResponseType.OK)

            label.set_text(f"{get_message('Found')}: {count}")
            area.pack_start(label, True, True, 0)
            self.show_all()

    def __init__(self, app):
        super().__init__(app)

    def exec(self):
        if not self.app.is_enigma:
            self.app.show_error_message("Neutrino is not supported!")
            return

        view = self.app.bouquets_view
        model, paths = view.get_selection().get_selected_rows()
        if not paths:
            self.app.show_info_message("No selected item!")
        else:
            bqs = self.app.current_bouquets
            to_remove = defaultdict(set)

            for p in paths:
                bq_id = f"{model[p][Column.BQ_NAME]}:{model[p][Column.BQ_TYPE]}"
                bq = bqs.get(bq_id, None)
                if bq:
                    exist = set()
                    for i, s in enumerate(bq):
                        res = get_iptv_data(s)
                        if all(res):
                            if res[-1] in exist:
                                to_remove[bq_id].add(i)
                            else:
                                exist.add(res[-1])

            dialog = self.CleanupDialog(to_remove, transient_for=self.app.app_window)

            if dialog.run() == Gtk.ResponseType.OK:
                bq_selected = self.app.check_bouquet_selection()
                count = 0
                for b, indexes in to_remove.items():
                    if b == bq_selected:
                        # Processing selected bouquet list if it is selected for cleaning.
                        model = self.app.fav_view.get_model()
                        to_remove = [row.iter for i, row in enumerate(model) if i in indexes]
                        gen = self.app.remove_favs(to_remove, model)
                        GLib.idle_add(lambda: next(gen, False))
                        count += len(to_remove)
                    else:
                        bq = bqs.get(b)
                        bq_size = len(bq)
                        [bq.pop(i) for i in sorted(indexes, reverse=True)]
                        count += bq_size - len(bq)

                self.app.show_info_message(f"{get_message('Done!')} {get_message('Removed')}: {count}")

            dialog.destroy()


if __name__ == "__main__":
    pass

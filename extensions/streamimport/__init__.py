# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2023-2026 Dmitriy Yefremov
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
from enum import IntEnum
from io import BytesIO
from itertools import groupby

import requests
from gi.repository import Gtk, Gdk, GLib

from app.commons import run_task
from app.eparser import Service
from app.eparser.ecommons import BqServiceType
from app.eparser.iptv import MARKER_FORMAT, get_picon_id, get_fav_id
from app.settings import SettingsType
from app.ui.main_helper import update_toggle_model, update_popup_filter_model, get_base_itrs, scroll_to, on_popup_menu, \
    get_pixbuf_from_data, get_base_model, get_base_paths
from app.ui.uicommons import IPTV_ICON, Column, UI_RESOURCES_PATH
from extensions import BaseExtension


class Streamimport(BaseExtension):
    LABEL = "Advanced streams import"
    VERSION = "1.2"

    def __init__(self, app):
        super().__init__(app)
        self._dialog = ImportDialog(self)

    def exec(self):
        self._dialog.show()


class ImportDialog(Gtk.Window):
    PARAMS = re.compile(r'(\S+)="(.*?)"')

    class Column(IntEnum):
        LOGO = 0
        NAME = 1
        GROUP = 2
        SELECTED = 3
        ID = 4
        URL = 5
        LOGO_URL = 6
        TOOLTIP = 7

    def __init__(self, plugin, **kwargs):
        super().__init__(title=Streamimport.LABEL,
                         destroy_with_parent=True,
                         window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
                         transient_for=plugin.app.app_window,
                         default_width=560,
                         icon_name="demon-editor",
                         **kwargs)

        self._plugin = plugin
        self._app = plugin.app
        self._groups = set()

        _base_path = os.path.dirname(__file__)
        builder = Gtk.Builder.new_from_file(f"{_base_path}{os.sep}dialog.ui")

        self.add(builder.get_object("main_box"))
        self._view = builder.get_object("view")
        self._popup_menu = builder.get_object("popup_menu")
        self._select_all_item = builder.get_object("select_all_item")
        self._remove_selection_item = builder.get_object("remove_selection_item")
        self._view.connect("select-all", lambda v: self.update_selection(True))
        self._view.connect_data("button-press-event", self.on_button_press)
        self._select_all_item.connect("activate", lambda i: self.update_selection(True))
        self._remove_selection_item.connect("activate", lambda i: self.update_selection(False))

        self._model = builder.get_object("model")
        self._filter_model = builder.get_object("filter_model")
        self._filter_model.set_visible_func(self.filter_function)
        self._filter_group_model = builder.get_object("filter_group_list_store")
        self._filter_entry = builder.get_object("filter_entry")
        self._filter_entry.connect("search-changed", self.on_filter_changed)
        renderer_toggle = builder.get_object("filter_group_renderer_toggle")
        renderer_toggle.connect("toggled", self.on_group_toggled)

        self._chooser_button = builder.get_object("file_chooser_button")
        self._chooser_button.connect("file-set", self.on_file_set)
        self._url_entry = builder.get_object("url_entry")
        self._url_entry.connect("activate", self.on_url_set)
        self._url_entry.connect("focus-out-event", lambda e, ev: e.set_name("GtkEntry"))

        self._input_text_view = builder.get_object("input_text_view")
        self._input_text_view.get_buffer().connect("paste-done", self.on_paste_text)
        builder.get_object("selected_renderer").connect("toggled", self.on_selected_toggled)
        builder.get_object("version_label").set_text(f"Ver: {Streamimport.VERSION}")

        self._service_type_box = builder.get_object("service_type_box")
        self._single_bq_button = builder.get_object("single_bq_button")
        self._split_bq_button = builder.get_object("split_bq_button")
        self._sub_bq_button = builder.get_object("sub_bq_button")
        builder.get_object("import_button").connect("clicked", self.on_import)
        self.connect("hide", self.clear_data)
        self.connect("delete-event", self.on_destroy)
        # Neutrino.
        builder.get_object("options_grid").set_visible(self._app.is_enigma)
        # Channel logos.
        column = builder.get_object("name_column")
        column.set_cell_data_func(builder.get_object("logo_renderer"), self.logo_data_func)
        self._view.connect("query-tooltip", self.on_view_query_tooltip)

        style_provider = Gtk.CssProvider()
        style_provider.load_from_path(f"{UI_RESOURCES_PATH}style.css")
        self._url_entry.get_style_context().add_provider_for_screen(Gdk.Screen.get_default(), style_provider,
                                                                    Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def on_destroy(self, window, event):
        """ Used to prevent window deletion and destroying. """
        window.hide()
        return True

    def logo_data_func(self, column, renderer, model, itr, data):
        if not model.get_value(itr, self.Column.LOGO):
            renderer.set_property("pixbuf", IPTV_ICON)

    def on_view_query_tooltip(self, view, x, y, keyboard_mode, tooltip):
        dest = view.get_dest_row_at_pos(x, y)
        if not dest:
            return False

        path, pos = dest
        model = view.get_model()
        row = model[path][:]
        tooltip.set_text(row[self.Column.NAME])
        tooltip.set_icon(row[self.Column.LOGO])
        view.set_tooltip_row(tooltip, path)

        url = row[self.Column.LOGO_URL]
        if url and not row[self.Column.LOGO]:
            self.update_logo(url, model, path)

        return True

    @run_task
    def update_logo(self, url, model, path):
        itr = get_base_itrs([model.get_iter(path)], model)[0]
        model = get_base_model(model)
        try:
            with requests.get(url=url, stream=True) as resp:
                if resp.status_code == 200:
                    buf = BytesIO()
                    for data in resp.iter_content(chunk_size=32):
                        buf.write(data)

                    buf.seek(0)
                    pix = get_pixbuf_from_data(buf.read(), 64, 64)
                    if pix:
                       GLib.idle_add(model.set_value, itr, self.Column.LOGO, pix)
        except requests.exceptions.ConnectionError as e:
            self.log(f"Error [update logo]: {e}")

    def clear_data(self, widget=None):
        self._model.clear()
        self._groups.clear()
        self.update_groups()
        self._filter_entry.set_text("")

    def on_file_set(self, button):
        self.clear_data()

        path = button.get_filename()
        if not os.path.isfile(path):
            return

        gen = self.update_from_file(path)
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def on_url_set(self, entry):
        self.clear_data()
        self._url_entry.set_progress_fraction(0)

        gen = self.update_from_url(entry.get_text())
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

    def on_paste_text(self, buffer, clip):
        self.clear_data()

        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        gen = self.process_data(text.splitlines())
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)

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

    def update_from_url(self, url):
        self._url_entry.set_name("GtkEntry" if url else "digit-entry")
        if not url:
            return

        resp = requests.get(url, headers={}, timeout=5, stream=True)

        if resp.status_code == 200:
            downloaded = 0
            # Get total playlist byte size
            data_size = int(resp.headers.get("content-length", 15))
            encoding = resp.encoding or resp.apparent_encoding or "utf-8"

            from tempfile import TemporaryFile

            with TemporaryFile() as tf:
                completed = set()

                for data in resp.iter_content(chunk_size=32):
                    downloaded += len(data)
                    tf.write(data)
                    progress = downloaded / data_size
                    done = int(100 * progress)
                    yield True
                    self._url_entry.set_progress_fraction(progress)
                    if done % 25 == 0 and done not in completed:
                        completed.add(done)
                        self.log(f"Downloading playlist...{done}%" if done < 100 else "Playlist download complete.")
                tf.seek(0)
                yield from self.process_data(str(tf.read(), encoding=encoding, errors="ignore").splitlines())

            if downloaded < data_size:
                self.log("Error. The file size is incorrect.")
        else:
            msg = f"HTTP error {resp.status_code} while retrieving from {url}!"
            self._app.show_error_message(msg)
            self.log(msg)
        yield True

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
                line, sep, name = line.rpartition(",")
                params = dict(self.PARAMS.findall(line))
                group = params.get("group-title", None)
                name = params.get("tvg-name", name)
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
                group = group or "No Group"
                self._groups.add(group)

                yield self._model.append((None, name, group, True, ch_id, url, logo, None))

        self.update_groups()
        yield True

    def on_button_press(self, view, event):
        empty = bool(len(view.get_model()))
        self._select_all_item.set_sensitive(empty)
        self._remove_selection_item.set_sensitive(empty)
        on_popup_menu(self._popup_menu, event)

    def update_selection(self, select):
        model = self._view.get_model()
        iters = get_base_itrs((r.iter for r in model), model)
        [self._model.set_value(itr, self.Column.SELECTED, select) for itr in iters]

    def on_selected_toggled(self, renderer, path):
        model = self._view.get_model()
        itr = get_base_itrs((model.get_iter(path),), model).pop()
        self._model.set_value(itr, self.Column.SELECTED, not renderer.get_active())

    def on_group_toggled(self, renderer, path):
        update_toggle_model(self._filter_group_model, path, renderer)
        self._groups.clear()
        self._groups.update({r[0] for r in self._filter_group_model if r[1]})
        self.on_filter_changed()

    def update_groups(self):
        update_popup_filter_model(self._filter_group_model, self._groups)
        list(map(lambda g: self._filter_group_model.append((g, True)), sorted(self._groups, reverse=True)))

    def on_filter_changed(self, entry=None):
        self._filter_model.refilter()

    def filter_function(self, model, itr, data):
        if any((model is None, model == "None")):
            return True

        txt, grp = model[itr][self.Column.NAME], model[itr][self.Column.GROUP]
        txt = txt.upper() if txt else ""

        return self._filter_entry.get_text().upper() in txt and grp in self._groups

    def on_import(self, button):
        settings_type = self._app.app_settings.setting_type
        model = self._app.bouquets_view.get_model()

        if settings_type is SettingsType.ENIGMA_2:
            itr = model.get_iter_first()
        else:
            itr = model.get_iter(Gtk.TreePath.new_from_indices([len(model) - 1]))

        if not itr:
            self._app.show_error_message("Error. Load your data first!")
            return

        service_rows = [r for r in self._view.get_model() if r[self.Column.SELECTED]]
        if not service_rows:
            self._app.show_error_message("Error. No channels selected!")
            return

        if settings_type is SettingsType.ENIGMA_2:
            if not self._single_bq_button.get_active():
                def grouper(row):
                    return row[self.Column.GROUP]

                service_rows = groupby(sorted(service_rows, key=grouper), key=grouper)

        root_path = model.get_path(itr)
        bq_itr = itr

        if self._single_bq_button.get_active() or settings_type is SettingsType.NEUTRINO_MP:
            bq_itr = self.append_bouquet("IPTV", model, itr, service_rows, settings_type)
        elif self._split_bq_button.get_active():
            for g, g_services in service_rows:
                bq_itr = self.append_bouquet(g, model, itr, g_services, settings_type)
        else:
            itr = self.append_bouquet("IPTV", model, itr, (), settings_type)
            bq_itr = itr
            for g, g_services in service_rows:
                self.append_bouquet(g, model, itr, g_services, settings_type)

        scroll_to(model.get_path(bq_itr), self._app.bouquets_view, [root_path])
        self._app.show_info_message("Done!")

    def append_bouquet(self, name, model, itr, service_rows, settings_type):
        """ Adds new bouquet and returns iter of appended row. """
        bqs = self._app.current_bouquets
        cur_services = self._app.current_services
        bq_type = model.get_value(itr, Column.BQ_TYPE)

        bq_name = self.get_bouquet_name(bqs, name, bq_type)
        services = self.get_group_services(service_rows, settings_type)
        bqs[f"{bq_name}:{bq_type}"] = [s.fav_id for s in services]
        cur_services.update({s.fav_id: s for s in services})
        bq = (bq_name, None, None, bq_type)
        return model.append(itr, bq)

    def get_group_services(self, rows, settings_type):
        params = [0, 0, 0, 0]

        aggr = [None] * 10
        s_aggr = aggr[: -3]
        m_name = BqServiceType.MARKER.name
        st = BqServiceType.IPTV.name
        p_id = "1_0_1_0_0_0_0_0_0_0.png"
        picon = None
        srv_type = None
        if settings_type is SettingsType.ENIGMA_2:
            srv_type = self._service_type_box.get_active_id()

        grp_services = []
        groups = set()
        m_counter = 0
        sid_counter = 0
        for rs in rows:
            if settings_type is SettingsType.ENIGMA_2:
                grp = rs[self.Column.GROUP]
                if grp and grp not in groups:
                    groups.add(grp)
                    m_counter += 1
                    fav_id = MARKER_FORMAT.format(m_counter, grp, grp)
                    grp_services.append(Service(None, None, None, grp, *aggr[0:3], m_name, *aggr, fav_id, None))
            sid_counter += 1
            params[0] = sid_counter
            name, url = rs[self.Column.NAME], rs[self.Column.URL]
            fav_id = get_fav_id(url, name, settings_type, params, srv_type)
            if settings_type is SettingsType.ENIGMA_2:
                p_id = get_picon_id(params, srv_type)

            if all((name, url, fav_id)):
                srv = Service(None, None, IPTV_ICON, name, *aggr[0:3], st, picon, p_id, *s_aggr, url, fav_id, None)
                grp_services.append(srv)
            else:
                self.log(f"Import error: name[{name}], url[{url}], fav id[{fav_id}]")

        return grp_services

    def get_bouquet_name(self, bouquets, base_name, bq_type):
        count = 0
        key = f"{base_name}:{bq_type}"
        bq_name = base_name
        #  Generating name of new bouquet.
        while key in bouquets:
            count += 1
            bq_name = f"{base_name}{count}"
            key = f"{bq_name}:{bq_type}"

        return bq_name

    def log(self, msg):
        self._plugin.log(msg)


if __name__ == "__main__":
    pass

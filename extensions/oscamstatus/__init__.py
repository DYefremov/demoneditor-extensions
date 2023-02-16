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

import json
import os
from enum import Enum
from threading import Thread
from urllib.request import (urlopen, Request, HTTPPasswordMgrWithDefaultRealm, HTTPDigestAuthHandler, build_opener,
                            install_opener)

from gi.repository import GLib, Gtk, GObject

from extensions import BaseExtension


class OSCRequest(str, Enum):
    READERS = "part=readerlist"


class Oscamstatus(BaseExtension):
    """ A simple extension to display OSCam status. """

    LABEL = "OSCam status"

    def __init__(self, app):
        super().__init__(app)
        app.connect("profile-changed", self.on_profile_changed)
        # Settings.
        self._host = app.app_settings.host
        self._base_url = None
        self._url = None
        self._config = self.get_config()
        self.init_urls()

        _base_path = os.path.dirname(__file__)
        builder = Gtk.Builder.new_from_file(f"{_base_path}{os.sep}dialog.ui")
        # Settings.
        self._user_entry = builder.get_object("user_entry")
        self._password_entry = builder.get_object("password_entry")
        self._port_entry = builder.get_object("port_entry")
        self._refresh_button = builder.get_object("refresh_spin_button")
        builder.get_object("apply_config_button").connect("clicked", self.on_apply_config)

        self._window = builder.get_object("window")
        self._window.set_title(self.LABEL)
        refresh_interval = self._config.get('refresh_interval', 3)
        self._window.connect("show", lambda w: GLib.timeout_add_seconds(refresh_interval, self.update_status))
        self._window.connect("delete-event", self.on_close_window)
        self._stack = builder.get_object("stack")
        self._stack.connect("notify::visible-child-name", self.on_page_changed)
        self._restart_button = builder.get_object("restart_button")
        self._restart_button.connect("clicked", self.on_restart)
        self._version_label = builder.get_object("version_label")
        self._readers_count_label = builder.get_object("readers_count_label")

        self._readers_view = builder.get_object("readers_view")
        GObject.signal_new("data-changed", self._readers_view, GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_PYOBJECT, (GObject.TYPE_PYOBJECT,))
        self._readers_view.connect("data-changed", self.on_data_changed)
        self._readers_view.connect("query-tooltip", self.on_readers_query_tooltip)
        model = self._readers_view.get_model()
        model.connect("row-deleted", self.on_readers_model_changed)
        model.connect("row-inserted", self.on_readers_model_changed)

        self.init_auth()

    def init_urls(self):
        self._base_url = f"http://{self._host}:{self._config.get('port', '8080')}/oscamapi.json?"
        self._url = f"{self._base_url}{OSCRequest.READERS}"

    def exec(self):
        self._window.show()

    def init_auth(self):
        pass_mgr = HTTPPasswordMgrWithDefaultRealm()
        pass_mgr.add_password(None, self._base_url, self._config.get("user", ""), self._config.get("password", ""))
        auth_handler = HTTPDigestAuthHandler(pass_mgr)
        opener = build_opener(auth_handler)
        install_opener(opener)

    def update_status(self):
        active = self._window.get_visible()
        if active:
            Thread(target=self.refresh_data, daemon=True).start()
        return active

    def on_profile_changed(self, app, prf):
        self._readers_view.get_model().clear()
        self._host = app.app_settings.host
        self.init_auth()
        self.log("profile changed")

    def refresh_data(self):
        data = None
        try:
            with urlopen(Request(self._url, data=None), timeout=2) as f:
                if f.status == 200:
                    data = json.load(f)
                    self.log("Update state")
                else:
                    self.log(f"Error: {f.status}")
        except OSError as e:
            self.log(f"Error: {e}")

        GLib.idle_add(self._readers_view.emit, "data-changed", data)

    def on_data_changed(self, list_box, data):
        model = self._readers_view.get_model()
        if not data:
            model.clear()
            return

        readers = {row[-1]["label"]: row.iter for row in model}
        osc = data.get("oscam", None)
        if osc:
            self._version_label.set_text(osc.get("version", "N/A"))
            for r in osc.get("readers"):
                enabled = bool(int(r.get("enabled", 0)))
                reader = (r.get("label", None), r.get("protocol", None), enabled, r)
                itr = readers.pop(r.get("label"), None)
                if itr:
                    model[itr][:] = reader
                else:
                    model.append(reader)
            # Removal if some readers were not found during the update.
            [model.remove(i) for i in readers.values()]

    def on_readers_query_tooltip(self, view, x, y, keyboard_mode, tooltip):
        result = view.get_dest_row_at_pos(x, y)
        if not result:
            return False

        path, pos = result
        data = view.get_model()[path][-1]
        if data:
            stats = data.get("stats")
            tooltip.set_markup("\n".join(f'<span weight="bold">{str(k).title()}</span>: {v}' for k, v in stats.items()))
            view.set_tooltip_row(tooltip, path)
            return True

        return False

    def on_restart(self, button):
        self.app.show_error_message("Not implemented yet!")

    def on_readers_model_changed(self, model, path, itr=None):
        self._readers_count_label.set_text(str(len(model)))

    def on_apply_config(self, button):
        self._config["user"] = self._user_entry.get_text()
        self._config["password"] = self._password_entry.get_text()
        self._config["port"] = self._port_entry.get_text()
        self._config["refresh_interval"] = self._refresh_button.get_value()

        self.config = self._config
        self.init_urls()
        self.init_auth()
        self._stack.set_visible_child_name("readers")

    def get_config(self):
        return self.config or {"port": '8080', "user": "oscam", "password": "oscam", "refresh_interval": 3}

    def on_page_changed(self, stack, param):
        if stack.get_visible_child_name() == "settings":
            self._user_entry.set_text(self._config.get("user", "oscam"))
            self._password_entry.set_text(self._config.get("password", "oscam"))
            self._port_entry.set_text(self._config.get("port", "8080"))
            self._refresh_button.set_value(self._config.get("refresh_interval", 3))

    def on_close_window(self, window, event):
        """ Prevents window destroying when the close button is clicked. """
        window.hide()
        return True


if __name__ == '__main__':
    pass

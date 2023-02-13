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
from threading import Thread
from urllib.request import (urlopen, Request, HTTPPasswordMgrWithDefaultRealm, HTTPDigestAuthHandler, build_opener,
                            install_opener)

from gi.repository import GLib, Gtk, GObject

from extensions import BaseExtension


class Oscamstatus(BaseExtension):
    """ A simple extension to display OSCam status. """

    LABEL = "OSCam status"

    def __init__(self, app):
        super().__init__(app)
        app.connect("profile-changed", self.on_profile_changed)
        # Settings.
        self._host = app.app_settings.host
        self._settings = self.get_settings()
        self._url = f"http://{self._host}:{self._settings.get('port', '8080')}/oscamapi.json?part=readerlist"
        refresh_interval = self._settings.get('refresh_interval', 3)

        _base_path = os.path.dirname(__file__)
        builder = Gtk.Builder.new_from_file(f"{_base_path}{os.sep}dialog.ui")

        self._user_entry = builder.get_object("user_entry")
        self._password_entry = builder.get_object("password_entry")
        self._port_entry = builder.get_object("port_entry")
        self._refresh_button = builder.get_object("refresh_spin_button")
        builder.get_object("apply_settings_button").connect("clicked", self.on_save_settings)

        self._user_entry.set_text(self._settings.get("user", "oscam"))
        self._password_entry.set_text(self._settings.get("password", "oscam"))
        self._port_entry.set_text(self._settings.get("port", "8080"))
        self._refresh_button.set_value(refresh_interval)

        self._window = builder.get_object("window")
        self._window.set_title(self.LABEL)
        self._window.connect("show", lambda w: GLib.timeout_add_seconds(refresh_interval, self.update_status))
        self._window.connect("delete-event", self.on_close_window)

        self._version_label = builder.get_object("version_label")
        self._readers_view = builder.get_object("readers_view")
        GObject.signal_new("data-changed", self._readers_view, GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_PYOBJECT, (GObject.TYPE_PYOBJECT,))
        self._readers_view.connect("data-changed", self.on_data_changed)

        self.init_auth()

    def exec(self):
        self._window.show()

    def init_auth(self):
        pass_mgr = HTTPPasswordMgrWithDefaultRealm()
        pass_mgr.add_password(None, self._url, "oscam", "oscam")
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
        try:
            with urlopen(Request(self._url, data=None), timeout=2) as f:
                if f.status == 200:
                    self._readers_view.emit("data-changed", json.load(f))
                    self.log("Update state")
                else:
                    self.log(f"Error: {f.status}")
        except OSError as e:
            self.log(f"Error: {e}")

    def on_data_changed(self, list_box, data):
        model = self._readers_view.get_model()
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

    def on_save_settings(self, button):
        self.app.show_error_message("Not implemented yet!")

    def get_settings(self):
        return {"port": '8080', "user": "oscam", "password": "oscam", "refresh_interval": 3}

    def on_close_window(self, window, event):
        """ Prevents window destroying when the close button is clicked. """
        window.hide()
        return True


if __name__ == '__main__':
    pass

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


from app.ui.uicommons import MOD_MASK, KeyboardKey
from extensions import BaseExtension


class Undo(BaseExtension):
    LABEL = "Undo"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        if not hasattr(app, "VERSION") or app.VERSION < "3.14.4":
            msg = "Init error. Minimum required app version >= 3.14.4."
            self.log(msg)
            self.app.show_error_message(f"[{self.__class__.__name__}] {msg}")
            return

        self._removed = []
        self._fav_model = app.fav_view.get_model()

        app.connect("profile-changed", self.clear)
        app.connect("bouquet-changed", self.clear)
        app.connect("fav-removed", self.on_fav_removed)
        app.fav_view.connect("key-press-event", self.on_fav_key_press)

    def clear(self, app, data):
        self._removed.clear()

    def on_fav_removed(self, app, removed):
        self._removed.append(removed)

    def on_fav_key_press(self, view, event):
        if not self._removed:
            return

        key = KeyboardKey(event.hardware_keycode)
        if key is not KeyboardKey.Z or not event.state & MOD_MASK:
            return

        [self._fav_model.insert(s[0], s[1]) for s in reversed(self._removed.pop())]


if __name__ == "__main__":
    pass

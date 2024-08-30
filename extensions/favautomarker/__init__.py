# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2024 Dmitriy Yefremov
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

from extensions import BaseExtension
from gi.repository import GLib


class Favautomarker(BaseExtension):
    LABEL = "Mark not in bouquets"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        if not hasattr(app, "VERSION") or app.VERSION < "3.11.0":
            msg = "Init error. Minimum required app version >= 3.11.0."
            self.log(msg)
            self.app.show_error_message(f"[{self.__class__.__name__}] {msg}")
            return

        app.connect("fav-added", self.update_mark)
        app.connect("fav-removed", self.update_mark)
        app.connect("bouquet-removed", self.update_mark)
        app.connect("data-load-done", self.update_mark)

    def update_mark(self, app, data=None):
        gen = self.app.mark_not_in_bouquets()
        GLib.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_LOW)


if __name__ == "__main__":
    pass

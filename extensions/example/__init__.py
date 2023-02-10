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


from gi.repository import Gtk

from extensions import BaseExtension


class Example(BaseExtension):
    """ An example of a simple extension class. """
    LABEL = "Example extension"

    def __init__(self, app):
        super().__init__(app)
        self._window = Gtk.Window(title=self.LABEL, destroy_with_parent=True, modal=True)
        self._window.set_default_size(320, 140)
        self._window.set_transient_for(app.app_window)
        self._window.set_application(app)
        self._window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        button = Gtk.Button("Show message!", visible=True)
        button.connect("clicked", self.on_show_message)
        self._window.add(button)
        self._window.connect("delete-event", self.on_destroy)

    def exec(self):
        self._window.show()

    def on_show_message(self, button):
        self.app.show_info_message("Hello from 'Example' extension!")

    def on_destroy(self, window, event):
        """ Used to hide window instead of destroying. """
        window.hide()
        return True


if __name__ == '__main__':
    pass

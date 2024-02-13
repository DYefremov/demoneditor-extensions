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


import os
import struct
from datetime import datetime
from io import BytesIO
from itertools import chain
from shutil import copyfileobj

from gi.repository import GLib

from app.connections import UtfFTP
from app.ui.dialogs import show_dialog, DialogType
from app.ui.tasks import BGTaskWidget
from app.ui.uicommons import Page, Column, Gtk
from extensions import BaseExtension


class Epgexport(BaseExtension):
    LABEL = "EPG Export"
    EMBEDDED = True
    VERSION = "1.0"

    def __init__(self, app):
        super().__init__(app)

        self._f_name = "epg.dat"
        self._cache = None
        self._xmltv_button = None
        self._send_on_done = True

        # Checking for the required version.
        if not hasattr(app, "DATA_SEND_PAGES"):
            msg = "Init error. Minimum required app version >= 3.9.0."
            self.log(msg)
            self.app.show_error_message(f"[{self.__class__.__name__}] {msg}")
            return

        app.DATA_SEND_PAGES.add(Page.EPG)
        app._stack_epg_box.connect("realize", self.on_epg_tab_realize)
        app.connect("data-send", self.on_data_send)

    def on_epg_tab_realize(self, widget):
        from app.ui.epg.epg import EpgTool

        children = widget.get_children()
        if not children or not isinstance(children[0], EpgTool):
            self.log("Initialization error [EPG tab].")
            return

        tool = children[0]
        self._xmltv_button = tool._src_xmltv_button
        self.app.connect("epg-cache-initialized", self.on_cache_init)
        self.app.connect("epg-cache-updated", self.on_cache_init)

    def on_cache_init(self, tool, cache):
        from app.ui.epg.epg import TabEpgCache

        if isinstance(cache, TabEpgCache):
            self._cache = cache

    def on_data_send(self, app, page):
        if page is not Page.EPG:
            return

        if self._xmltv_button.get_active():
            self.send_data()
        else:
            self.app.show_error_message("Load XML TV data first!")

    def send_data(self):
        if not self._cache:
            self.app.show_error_message("Error. EPG cache is not initialized!")
            self.log("EPG cache is not initialized!")
            return

        msg = ("\n\t This operation will overwrite\n"
               "the current EPG cache file of your receiver!\n\n\t\t\tAre you sure?\n\n\n"
               "\t\t\t\tATTENTION\n"
               "After the operation is completed, load the cache data\n"
               "         manually using the receiver menu!")
        if show_dialog(DialogType.QUESTION, self.app.app_window, msg) != Gtk.ResponseType.OK:
            return

        self.app.change_action_state("on_logs_show", GLib.Variant.new_boolean(True))
        self.log("Checking bouquets selection...")
        current = self.app.current_bouquets
        model, paths = self.app.bouquets_view.get_selection().get_selected_rows()
        selected_bouquets = current.keys() & {f"{model[p][Column.BQ_NAME]}:{model[p][Column.BQ_TYPE]}" for p in paths}
        self.log(f"Selected bouquets: {len(selected_bouquets)}")

        if not selected_bouquets:
            self.app.show_error_message("Error. No bouquet is selected!")
            return

        services = self.app.current_services
        events = self._cache.events
        selected_services = (services[s] for s in chain.from_iterable(current[b] for b in selected_bouquets))
        services = [(s, events[s.service]) for s in selected_services if s.service in events]
        self.log(f"Services with EPG in cache: {len(services)}")
        # Processing data.
        path = f"{self.app.app_settings.profile_data_path}epg{os.sep}"
        self.process_dat(path, services)

    def process_dat(self, path, services):
        msg = f"Creating '{self._f_name}' file..."
        self.log(msg)
        writer = EpgWriter(f"{path}{self._f_name}", services, self.log)

        def process():
            writer.write()
            if self._send_on_done:
                self.send_dat(path)

        task = BGTaskWidget(self.app, msg, process, )
        self.app.emit("add-background-task", task)

    def send_dat(self, path):
        settings = self.app.app_settings
        with UtfFTP(host=settings.host, user=settings.user, passwd=settings.password) as ftp:
            ftp.encoding = "utf-8"
            try:
                self.log(f"Current dir for '{self._f_name}': {settings.epg_dat_path}")
                ftp.cwd(settings.epg_dat_path)
            except Exception as e:
                self.log(e)
            else:
                resp = ftp.send_file(self._f_name, path, self.log)
                if resp.startswith("2"):
                    self.app.show_info_message("Done!", Gtk.MessageType.INFO)


class EpgWriter:
    """ The epd.dat file writing class.

        The base writing code and algorithm was taken from the 'epgdat.py' file of EPGImport plugin from here:
        https://github.com/OpenPLi/enigma2-plugin-extensions-epgimport
    """
    # This table is used by CRC32 routine below (used by Dreambox for computing REF DESC value).
    # The original DM routine is a modified CRC32 standard routine, so cannot use Python standard binascii.crc32()
    CRC_TABLE = (0x00000000, 0x04C11DB7, 0x09823B6E, 0x0D4326D9, 0x130476DC, 0x17C56B6B, 0x1A864DB2, 0x1E475005,
                 0x2608EDB8, 0x22C9F00F, 0x2F8AD6D6, 0x2B4BCB61, 0x350C9B64, 0x31CD86D3, 0x3C8EA00A, 0x384FBDBD,
                 0x4C11DB70, 0x48D0C6C7, 0x4593E01E, 0x4152FDA9, 0x5F15ADAC, 0x5BD4B01B, 0x569796C2, 0x52568B75,
                 0x6A1936C8, 0x6ED82B7F, 0x639B0DA6, 0x675A1011, 0x791D4014, 0x7DDC5DA3, 0x709F7B7A, 0x745E66CD,
                 0x9823B6E0, 0x9CE2AB57, 0x91A18D8E, 0x95609039, 0x8B27C03C, 0x8FE6DD8B, 0x82A5FB52, 0x8664E6E5,
                 0xBE2B5B58, 0xBAEA46EF, 0xB7A96036, 0xB3687D81, 0xAD2F2D84, 0xA9EE3033, 0xA4AD16EA, 0xA06C0B5D,
                 0xD4326D90, 0xD0F37027, 0xDDB056FE, 0xD9714B49, 0xC7361B4C, 0xC3F706FB, 0xCEB42022, 0xCA753D95,
                 0xF23A8028, 0xF6FB9D9F, 0xFBB8BB46, 0xFF79A6F1, 0xE13EF6F4, 0xE5FFEB43, 0xE8BCCD9A, 0xEC7DD02D,
                 0x34867077, 0x30476DC0, 0x3D044B19, 0x39C556AE, 0x278206AB, 0x23431B1C, 0x2E003DC5, 0x2AC12072,
                 0x128E9DCF, 0x164F8078, 0x1B0CA6A1, 0x1FCDBB16, 0x018AEB13, 0x054BF6A4, 0x0808D07D, 0x0CC9CDCA,
                 0x7897AB07, 0x7C56B6B0, 0x71159069, 0x75D48DDE, 0x6B93DDDB, 0x6F52C06C, 0x6211E6B5, 0x66D0FB02,
                 0x5E9F46BF, 0x5A5E5B08, 0x571D7DD1, 0x53DC6066, 0x4D9B3063, 0x495A2DD4, 0x44190B0D, 0x40D816BA,
                 0xACA5C697, 0xA864DB20, 0xA527FDF9, 0xA1E6E04E, 0xBFA1B04B, 0xBB60ADFC, 0xB6238B25, 0xB2E29692,
                 0x8AAD2B2F, 0x8E6C3698, 0x832F1041, 0x87EE0DF6, 0x99A95DF3, 0x9D684044, 0x902B669D, 0x94EA7B2A,
                 0xE0B41DE7, 0xE4750050, 0xE9362689, 0xEDF73B3E, 0xF3B06B3B, 0xF771768C, 0xFA325055, 0xFEF34DE2,
                 0xC6BCF05F, 0xC27DEDE8, 0xCF3ECB31, 0xCBFFD686, 0xD5B88683, 0xD1799B34, 0xDC3ABDED, 0xD8FBA05A,
                 0x690CE0EE, 0x6DCDFD59, 0x608EDB80, 0x644FC637, 0x7A089632, 0x7EC98B85, 0x738AAD5C, 0x774BB0EB,
                 0x4F040D56, 0x4BC510E1, 0x46863638, 0x42472B8F, 0x5C007B8A, 0x58C1663D, 0x558240E4, 0x51435D53,
                 0x251D3B9E, 0x21DC2629, 0x2C9F00F0, 0x285E1D47, 0x36194D42, 0x32D850F5, 0x3F9B762C, 0x3B5A6B9B,
                 0x0315D626, 0x07D4CB91, 0x0A97ED48, 0x0E56F0FF, 0x1011A0FA, 0x14D0BD4D, 0x19939B94, 0x1D528623,
                 0xF12F560E, 0xF5EE4BB9, 0xF8AD6D60, 0xFC6C70D7, 0xE22B20D2, 0xE6EA3D65, 0xEBA91BBC, 0xEF68060B,
                 0xD727BBB6, 0xD3E6A601, 0xDEA580D8, 0xDA649D6F, 0xC423CD6A, 0xC0E2D0DD, 0xCDA1F604, 0xC960EBB3,
                 0xBD3E8D7E, 0xB9FF90C9, 0xB4BCB610, 0xB07DABA7, 0xAE3AFBA2, 0xAAFBE615, 0xA7B8C0CC, 0xA379DD7B,
                 0x9B3660C6, 0x9FF77D71, 0x92B45BA8, 0x9675461F, 0x8832161A, 0x8CF30BAD, 0x81B02D74, 0x857130C3,
                 0x5D8A9099, 0x594B8D2E, 0x5408ABF7, 0x50C9B640, 0x4E8EE645, 0x4A4FFBF2, 0x470CDD2B, 0x43CDC09C,
                 0x7B827D21, 0x7F436096, 0x7200464F, 0x76C15BF8, 0x68860BFD, 0x6C47164A, 0x61043093, 0x65C52D24,
                 0x119B4BE9, 0x155A565E, 0x18197087, 0x1CD86D30, 0x029F3D35, 0x065E2082, 0x0B1D065B, 0x0FDC1BEC,
                 0x3793A651, 0x3352BBE6, 0x3E119D3F, 0x3AD08088, 0x2497D08D, 0x2056CD3A, 0x2D15EBE3, 0x29D4F654,
                 0xC5A92679, 0xC1683BCE, 0xCC2B1D17, 0xC8EA00A0, 0xD6AD50A5, 0xD26C4D12, 0xDF2F6BCB, 0xDBEE767C,
                 0xE3A1CBC1, 0xE760D676, 0xEA23F0AF, 0xEEE2ED18, 0xF0A5BD1D, 0xF464A0AA, 0xF9278673, 0xFDE69BC4,
                 0x89B8FD09, 0x8D79E0BE, 0x803AC667, 0x84FBDBD0, 0x9ABC8BD5, 0x9E7D9662, 0x933EB0BB, 0x97FFAD0C,
                 0xAFB010B1, 0xAB710D06, 0xA6322BDF, 0xA2F33668, 0xBCB4666D, 0xB8757BDA, 0xB5365D03, 0xB1F740B4)

    LB_ENDIAN = '<'
    EPG_PROLEPTIC_ZERO_DAY = 678576

    def __init__(self, path, services, log_func=print):
        self.epg_dat_path = path
        self._services = services

        self.header1_srv_count = 0
        self.header2_desc_count = 0
        self.total_events = 0
        self._events = {}

        self.s_BB = struct.Struct("BB")
        self.s_BBB = struct.Struct("BBB")
        self.s_b_HH = struct.Struct(">HH")
        self.s_I = struct.Struct(self.LB_ENDIAN + "I")
        self.s_II = struct.Struct(self.LB_ENDIAN + "II")
        self.s_IIII = struct.Struct(self.LB_ENDIAN + "IIII")
        self.s_B3sHBB = struct.Struct("B3sHBB")
        self.s_B3sBBB = struct.Struct("B3sBBB")
        self.s_3sBB = struct.Struct("3sBB")

        self.log = log_func

    @staticmethod
    def get_crc32(crc_data, crc_type, crc_table=CRC_TABLE):
        """ CRC32 in Dreambox/DVB way (see CRC_TABLE).

            :param crc_data: description string
            :param crc_type: description type (1 byte 0x4d or 0x4e)
            :param crc_table: -> CRC_TABLE
         """
        crc = crc_table[crc_type & 0x000000ff]
        crc = ((crc << 8) & 0xffffff00) ^ crc_table[((crc >> 24) ^ len(crc_data)) & 0x000000ff]
        for d in crc_data:
            crc = ((crc << 8) & 0xffffff00) ^ crc_table[((crc >> 24) ^ d) & 0x000000ff]
        return crc

    @staticmethod
    def get_tl_hexconv(dt):
        return ((dt.hour % 10) + (16 * (dt.hour // 10)),
                (dt.minute % 10) + (16 * (dt.minute // 10)),
                (dt.second % 10) + (16 * (dt.second // 10)))

    def short_desc(self, desc):
        """ Assembling short description (type 0x4d , it's the Title) and compute its crc.

            0x15 -> UTF-8 encoding.
        """
        b_desc = desc.encode(encoding="utf-8", errors="ignore")[:240]
        b_data = self.s_3sBB.pack(b"eng", len(b_desc) + 1, 0x15) + b_desc + b"\0"
        return self.get_crc32(b_data, 0x4d), b_data

    def long_desc(self, desc):
        """ Assembling long description (type 0x4e) and compute its crc.

            Compute total number of descriptions, block 245 bytes each
            number of descriptions start to index 0
        """
        res = []
        b_desc = desc.encode(encoding="utf-8", errors="ignore")
        # Maximum number of data chunks. Used for limit the description size.
        max_count = 15
        desc_count = (len(b_desc) + 244) // 245
        if desc_count > max_count:
            desc_count = max_count

        for i in range(desc_count):
            ssub = b_desc[i * 245:i * 245 + 245] if i < max_count else b"..."
            b_data = self.s_B3sBBB.pack((i << 4) + (desc_count - 1), b"eng", 0x00, int(len(ssub) + 1), 0x15) + ssub
            res.append((self.get_crc32(b_data, 0x4e), b_data))
        return res

    def get_event(self, ed):
        title = ed.get("e2eventtitle", "")
        desc = ed.get("e2eventdescription", None) or title
        return ed.get("e2eventstart"), ed.get("e2eventduration"), self.short_desc(title), self.long_desc(desc)

    def write(self):
        epg_event_data_id = 0
        default_iptv_ref_detected = False
        def_ref_data = ("0", "0", "0")

        with BytesIO() as tf:
            for srv, ev in self._services:
                # sid, nid, tid.
                sd = srv.fav_id.split(":")
                if len(sd) == 4:
                    sid, nid, tid, _ = sd
                else:
                    sid, nid, tid = sd[3], sd[5], sd[4]
                    if (sid, nid, tid) == def_ref_data:
                        # Detecting IPTV services with default values of SID, NIT, TID.
                        if not default_iptv_ref_detected:
                            self.log("Detected IPTV service(s) with values for [SID, NID, TID] = 0. Skipping...")
                            default_iptv_ref_detected = True
                        continue

                try:
                    sid, nid, tid = int(sid, 16), int(nid, 16), int(tid, 16)
                except ValueError as e:
                    self.log(f"Getting service [{srv.service}] data error: {e}")
                    continue

                events = [self.get_event(d) for d in (e.event_data for e in ev)]
                tf.write(self.s_IIII.pack(sid, nid, tid, len(events)))
                self.header1_srv_count += 1

                s_bb = self.s_BB
                s_bbb = self.s_BBB
                s_i = self.s_I

                for event in events:
                    # **** (1) : create DESCRIPTION HEADER / DATA ****
                    event_header_size = 0
                    # Short description (title) [type 0x4d].
                    short_desc = event[2]
                    event_header_size += 4  # add 4 bytes for a single REF DESC (CRC32)
                    if short_desc[0] not in self._events:
                        # DESCRIPTION DATA
                        self._events[short_desc[0]] = [s_bb.pack(0x4d, len(short_desc[1])) + short_desc[1], 1]
                        self.header2_desc_count += 1
                    else:
                        self._events[short_desc[0]][1] += 1
                    # Long description [type 0x4e].
                    long_desc = event[3]
                    event_header_size += 4 * len(long_desc)  # add 4 bytes for a single REF DESC (CRC32)
                    for desc in long_desc:
                        if desc[0] not in self._events:
                            # DESCRIPTION DATA
                            self._events[desc[0]] = [s_bb.pack(0x4e, len(desc[1])) + desc[1], 1]
                            self.header2_desc_count += 1
                        else:
                            self._events[desc[0]][1] += 1

                    # EVENT HEADER (3 bytes: 0x01 , 0x00, 10 bytes + number of CRC32 * 4)
                    tf.write(s_bbb.pack(0x01, 0x00, 0x0a + event_header_size))
                    # Time.
                    event_time_hms = datetime.utcfromtimestamp(event[0])
                    event_length_hms = datetime.utcfromtimestamp(event[1])
                    dvb_date = event_time_hms.toordinal() - self.EPG_PROLEPTIC_ZERO_DAY
                    # EVENT DATA
                    epg_event_data_id += 1
                    pack_1 = self.s_b_HH.pack(epg_event_data_id, dvb_date)  # ID and DATE , always in BIG_ENDIAN
                    pack_2 = s_bbb.pack(*self.get_tl_hexconv(event_time_hms))  # Start
                    pack_3 = s_bbb.pack(*self.get_tl_hexconv(event_length_hms))  # Duration
                    pack_4 = s_i.pack(short_desc[0])  # Short  description (title).
                    for d in long_desc:
                        pack_4 += s_i.pack(d[0])  # REF DESC long

                    tf.write(pack_1 + pack_2 + pack_3 + pack_4)

            if len(self._events) > 0:
                self.finalize(tf)

    def finalize(self, header_data):
        with open(self.epg_dat_path, "wb") as dat_fd:
            # HEADER 1.
            pack_1 = struct.pack(self.LB_ENDIAN + "I13sI", 0x98765432, b'ENIGMA_EPG_V8', self.header1_srv_count)
            dat_fd.write(pack_1)
            # Write first EPG.DAT section.
            header_data.seek(0)
            copyfileobj(header_data, dat_fd)
            # HEADER 2
            s_ii = self.s_II
            pack_1 = self.s_I.pack(self.header2_desc_count)
            dat_fd.write(pack_1)
            # Event MUST BE WRITTEN IN ASCENDING ORDERED using HASH CODE as index.
            for temp in sorted(self._events.keys()):
                pack_2 = self._events[temp]
                pack_1 = s_ii.pack(temp, pack_2[1])
                dat_fd.write(pack_1 + pack_2[0])

            self.log("The 'epg.dat' file creation is complete.")


if __name__ == "__main__":
    pass

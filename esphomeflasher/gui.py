# This GUI is a fork of the brilliant https://github.com/marcelstoer/nodemcu-pyflasher
import re
import sys
import threading
from io import TextIOBase

import wx
import wx.adv
import wx.lib.inspection
import wx.lib.mixins.inspection
from wx.lib.embeddedimage import PyEmbeddedImage

from esphomeflasher.helpers import list_serial_ports

# pylint: disable=no-member

COLOR_RE = re.compile(r"(?:\033)(?:\[(.*?)[@-~]|\].*?(?:\007|\033\\))")
COLORS = {
    "black": wx.BLACK,
    "red": wx.RED,
    "green": wx.GREEN,
    "yellow": wx.YELLOW,
    "blue": wx.BLUE,
    "magenta": wx.Colour(255, 0, 255),
    "cyan": wx.CYAN,
    "white": wx.WHITE,
}
FORE_COLORS = {**COLORS, None: wx.WHITE}
BACK_COLORS = {**COLORS, None: wx.BLACK}


# See discussion at http://stackoverflow.com/q/41101897/131929
class RedirectText(TextIOBase):
    def __init__(self, text_ctrl):
        super().__init__()
        self._out = text_ctrl
        self._i = 0
        self._line = ""
        self._bold = False
        self._italic = False
        self._underline = False
        self._foreground = None
        self._background = None
        self._secret = False

    def _add_content(self, value):
        attr = wx.TextAttr()
        if self._bold:
            attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
        attr.SetTextColour(FORE_COLORS[self._foreground])
        attr.SetBackgroundColour(BACK_COLORS[self._background])
        wx.CallAfter(self._out.SetDefaultStyle, attr)
        wx.CallAfter(self._out.AppendText, value)

    def _write_line(self):
        pos = 0
        while True:
            match = COLOR_RE.search(self._line, pos)
            if match is None:
                break

            j = match.start()
            self._add_content(self._line[pos:j])
            pos = match.end()

            for code in match.group(1).split(";"):
                code = int(code)
                if code == 0:
                    self._bold = False
                    self._italic = False
                    self._underline = False
                    self._foreground = None
                    self._background = None
                    self._secret = False
                elif code == 1:
                    self._bold = True
                elif code == 3:
                    self._italic = True
                elif code == 4:
                    self._underline = True
                elif code == 5:
                    self._secret = True
                elif code == 6:
                    self._secret = False
                elif code == 22:
                    self._bold = False
                elif code == 23:
                    self._italic = False
                elif code == 24:
                    self._underline = False
                elif code == 30:
                    self._foreground = "black"
                elif code == 31:
                    self._foreground = "red"
                elif code == 32:
                    self._foreground = "green"
                elif code == 33:
                    self._foreground = "yellow"
                elif code == 34:
                    self._foreground = "blue"
                elif code == 35:
                    self._foreground = "magenta"
                elif code == 36:
                    self._foreground = "cyan"
                elif code == 37:
                    self._foreground = "white"
                elif code == 39:
                    self._foreground = None
                elif code == 40:
                    self._background = "black"
                elif code == 41:
                    self._background = "red"
                elif code == 42:
                    self._background = "green"
                elif code == 43:
                    self._background = "yellow"
                elif code == 44:
                    self._background = "blue"
                elif code == 45:
                    self._background = "magenta"
                elif code == 46:
                    self._background = "cyan"
                elif code == 47:
                    self._background = "white"
                elif code == 49:
                    self._background = None

        self._add_content(self._line[pos:])

    def write(self, string):
        # pylint: disable=invalid-name
        for s in string:
            if s == "\r":
                current_value = self._out.GetValue()
                last_newline = current_value.rfind("\n")
                wx.CallAfter(self._out.Remove, last_newline + 1, len(current_value))
                # self._line += '\n'
                self._write_line()
                self._line = ""
                continue
            self._line += s
            if s == "\n":
                self._write_line()
                self._line = ""
                continue

    def writable(self):
        return True

    def isatty(self) -> bool:
        return True


class FlashingThread(threading.Thread):
    def __init__(self, parent, firmware, port, show_logs=False):
        threading.Thread.__init__(self)
        self.daemon = True
        self._parent = parent
        self._firmware = firmware
        self._port = port
        self._show_logs = show_logs

    def run(self):
        try:
            from esphomeflasher.__main__ import run_esphomeflasher

            argv = ["esphomeflasher", "--port", self._port, self._firmware]
            if self._show_logs:
                argv.append("--show-logs")
            run_esphomeflasher(argv)
        except Exception as err:
            print(f"Unexpected error: {err}")
            raise


class MainFrame(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(
            self,
            parent,
            -1,
            title,
            size=(725, 650),
            style=wx.DEFAULT_FRAME_STYLE | wx.NO_FULL_REPAINT_ON_RESIZE,
        )

        self._firmware = None
        self._port = None

        self._init_ui()

        sys.stdout = RedirectText(self.console_ctrl)

        self.SetMinSize((640, 480))
        self.Centre(wx.BOTH)
        self.Show(True)

    def _init_ui(self):
        def on_reload(event):
            self.choice.SetItems(self._get_serial_ports())

        def on_clicked(event):
            self.console_ctrl.SetValue("")
            worker = FlashingThread(self, self._firmware, self._port)
            worker.start()

        def on_logs_clicked(event):
            self.console_ctrl.SetValue("")
            worker = FlashingThread(self, "dummy", self._port, show_logs=True)
            worker.start()

        def on_select_port(event):
            choice = event.GetEventObject()
            self._port = choice.GetString(choice.GetSelection())

        def on_pick_file(event):
            self._firmware = event.GetPath().replace("'", "")

        panel = wx.Panel(self)

        hbox = wx.BoxSizer(wx.HORIZONTAL)

        fgs = wx.FlexGridSizer(7, 2, 10, 10)

        self.choice = wx.Choice(panel, choices=self._get_serial_ports())
        self.choice.Bind(wx.EVT_CHOICE, on_select_port)
        bmp = Reload.GetBitmap()
        reload_button = wx.BitmapButton(
            panel,
            id=wx.ID_ANY,
            bitmap=bmp,
            size=(bmp.GetWidth() + 7, bmp.GetHeight() + 7),
        )
        reload_button.Bind(wx.EVT_BUTTON, on_reload)
        reload_button.SetToolTip("Reload serial device list")

        file_picker = wx.FilePickerCtrl(panel, style=wx.FLP_USE_TEXTCTRL)
        file_picker.Bind(wx.EVT_FILEPICKER_CHANGED, on_pick_file)

        serial_boxsizer = wx.BoxSizer(wx.HORIZONTAL)
        serial_boxsizer.Add(self.choice, 1, wx.EXPAND)
        serial_boxsizer.AddStretchSpacer(0)
        serial_boxsizer.Add(reload_button, 0, wx.ALIGN_NOT, 20)

        button = wx.Button(panel, -1, "Flash ESP")
        button.Bind(wx.EVT_BUTTON, on_clicked)

        logs_button = wx.Button(panel, -1, "View Logs")
        logs_button.Bind(wx.EVT_BUTTON, on_logs_clicked)

        self.console_ctrl = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        self.console_ctrl.SetFont(
            wx.Font(
                (0, 13),
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
            )
        )
        self.console_ctrl.SetBackgroundColour(wx.BLACK)
        self.console_ctrl.SetForegroundColour(wx.WHITE)
        self.console_ctrl.SetDefaultStyle(wx.TextAttr(wx.WHITE))

        port_label = wx.StaticText(panel, label="Serial port")
        file_label = wx.StaticText(panel, label="Firmware")

        console_label = wx.StaticText(panel, label="Console")

        fgs.AddMany(
            [
                # Port selection row
                port_label,
                (serial_boxsizer, 1, wx.EXPAND),
                # Firmware selection row (growable)
                file_label,
                (file_picker, 1, wx.EXPAND),
                # Flash ESP button
                (wx.StaticText(panel, label="")),
                (button, 1, wx.EXPAND),
                # View Logs button
                (wx.StaticText(panel, label="")),
                (logs_button, 1, wx.EXPAND),
                # Console View (growable)
                (console_label, 1, wx.EXPAND),
                (self.console_ctrl, 1, wx.EXPAND),
            ]
        )
        fgs.AddGrowableRow(4, 1)
        fgs.AddGrowableCol(1, 1)
        hbox.Add(fgs, proportion=2, flag=wx.ALL | wx.EXPAND, border=15)
        panel.SetSizer(hbox)

    def _get_serial_ports(self):
        ports = []
        for port, _ in list_serial_ports():
            ports.append(port)
        if not self._port and ports:
            self._port = ports[0]
        if not ports:
            ports.append("")
        return ports

    # Menu methods
    def _on_exit_app(self, event):
        self.Close(True)

    def log_message(self, message):
        self.console_ctrl.AppendText(message)


class App(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    # pylint: disable=invalid-name
    def OnInit(self):
        wx.SystemOptions.SetOption("mac.window-plain-transition", 1)
        self.SetAppName("esphome-flasher (Based on NodeMCU PyFlasher)")

        frame = MainFrame(None, "esphome-flasher (Based on NodeMCU PyFlasher)")
        frame.Show()

        return True


Exit = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABGdBTUEAAK/INwWK6QAAABl0"
    "RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAN1SURBVHjaYvz//z8DJQAggFhA"
    "xEpGRgaQMX+B+A8DgwYLM1M+r4K8P4+8vMi/P38Y3j18+O7Fs+fbvv7+0w9Uc/kHVG070HKA"
    "AGJBNg0omC5jZtynnpfHJeHkzPDmxQuGf6/eMIj+/yP+9MD+xFPrN8Reu3W3Gqi0D2IXAwNA"
    "AIEN+A/hpWuEBMwwmj6TgUVEjOHTo0cM9y9dZfj76ycDCysrg4K5FYMUvyAL7+pVnYfOXwJp"
    "6wIRAAHECAqDJYyMWpLmpmftN2/mYBEVZ3h38SLD9wcPGP6LioIN/7Z+PQM3UB3vv/8MXB/f"
    "MSzdvv3vpecvzfr+/z8HEEBMYFMYGXM0iwrAmu+sXcvw4OxZhqenTjEwAv3P9OsXw+unTxne"
    "6Osz3Ll3l+HvyzcMVlLSzMBwqgTpBQggsAG8MuKB4r9eM7zfv5PhHxMzg4qLCwPD0ycMDL9/"
    "MzD+/cvw/8kTBgUbGwbB1DSGe1cuMbD8+8EgwMPjCtILEEDgMOCSkhT+t20Nw4v7nxkkNuxm"
    "eLNmFYO0sCgDCwcHAwMzM4Pkl68MLzs7GGS6uhmOCwgxcD2+x8DLysID0gsQQGAD/gH99vPL"
    "dwZGDjaG/0An/z19goHp/z+Gn9dvgoP4/7dPDD9OnGD4+/0bA5uCAsPPW8DA5eACxxxAAIEN"
    "+PDuw/ufirJizE9fMzALCjD8efOO4dHObQx/d29k+PObgeHr268MQta2DCw8fAz/X75k+M/I"
    "xPDh1+9vIL0AAQQOg9dPX2x7w8TDwPL2FcOvI8cYxFs7GFjFpRl+PP/K8O3NVwZuIREGpe5u"
    "hp83rjF8u3iO4RsnO8OzHz8PgvQCBBA4GrsZGfUUtNXPWiuLsny59YxBch3Qdl4uhq/rNzP8"
    "BwYin58PAysbG8MFLy+Gnw9uM5xkYPp38fNX22X//x8DCCAmqD8u3bh6s+Lssy8MrCLcDC/8"
    "3Rl+LVvOwG1syMBrYcbwfetmhmsOdgy/795iuMXEwnDh89c2oJ7jIL0AAQR2wQRgXvgKNAfo"
    "qRIlJfk2NR42Rj5gEmb5+4/h35+/DJ+/fmd4DUyNN4B+v/DlWwcwcTWzA9PXQqBegACCGwAK"
    "ERD+zsBgwszOXirEwe7OzvCP5y/QCx/+/v/26vfv/R///O0GOvkII1AdKxCDDAAIIEZKszNA"
    "gAEA1sFjF+2KokIAAAAASUVORK5CYII="
)

Reload = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABGdBTUEAALGOfPtRkwAAACBj"
    "SFJNAAB6JQAAgIMAAPn/AACA6AAAdTAAAOpgAAA6lwAAF2+XqZnUAAAABmJLR0QA/wD/AP+g"
    "vaeTAAAACXBIWXMAAABIAAAASABGyWs+AAAACXZwQWcAAAAYAAAAGAB4TKWmAAACZUlEQVRI"
    "x7XVT4iXRRgH8M/8Mv9tUFgRZiBESRIhbFAo8kJ0EYoOwtJBokvTxUtBQnUokIjAoCi6+HiR"
    "CNKoU4GHOvQieygMJKRDEUiahC4UtGkb63TY+cnb6/rb3276vQwzzzPf5/9MKqW4kRj8n8s5"
    "53U55y03xEDOeRu+xe5ReqtWQDzAC3gTa3D7KP20nBrknDfhMB7vHH+Dj3AWxyPitxUZyDnv"
    "xsElPL6MT/BiRJwbaaBN6eamlH9yzmvxPp5bRibPYDIizg96pIM2pak2pSexGiLiEr7H3DIM"
    "3IMP/hNBm9It+BDzmGp6oeWcd+BIvdzFRZzGvUOnOtg6qOTrcRxP4ZVmkbxFxDQm8WVPtDMi"
    "tmIDPu7JJocpehnb8F1Tyo/XijsizmMX9teCwq1VNlvrdKFzZeOgTelOvFQPfurV5NE2pc09"
    "I/MR8TqewAxu68hmMd1RPzXAw1hXD9b3nL4bJ9qUdi0SzbF699ee6K9ObU6swoMd4Y42pYmm"
    "lNm6/91C33/RpvQG9jelzHeMnK4F7uK+ur49bNNzHeEdONSmNFH3f9R1gNdwrKZ0UeSc77fQ"
    "CCfxFqSveQA/9HTn8DM2d9I3xBk83ZQy3SNPFqb4JjwTEX9S56BN6SimjI857GtKea+ST+Cx"
    "6synETHssCuv6V5sd/UQXQur8VCb0tqmlEuYi4jPF1PsTvJGvFMjGfVPzOD5ppTPxvHkqseu"
    "Teku7MQm7MEjHfFXeLYp5ey4uRz5XLcpHbAwhH/jVbzblHJ5TG4s/aPN4BT2NKWcXA7xuBFs"
    "wS9NKRdXQr6kgeuBfwEbWdzTvan9igAAADV0RVh0Y29tbWVudABSZWZyZXNoIGZyb20gSWNv"
    "biBHYWxsZXJ5IGh0dHA6Ly9pY29uZ2FsLmNvbS/RLzdIAAAAJXRFWHRkYXRlOmNyZWF0ZQAy"
    "MDExLTA4LTIxVDE0OjAxOjU2LTA2OjAwdNJAnQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAxMS0w"
    "OC0yMVQxNDowMTo1Ni0wNjowMAWP+CEAAAAASUVORK5CYII="
)


def main():
    app = App(False)
    app.MainLoop()

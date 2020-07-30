# ESPHome-Flasher

ESPHome-Flasher is a utility app for the [ESPHome](https://esphome.io/)
framework and is designed to make flashing ESPs with ESPHome as simple as possible by:

 * Having pre-built binaries for most operating systems.
 * Hiding all non-essential options for flashing. All necessary options for flashing
   (bootloader, flash mode) are automatically extracted from the binary.

This project was originally intended to be a simple command-line tool,
but then I decided that a GUI would be nice. As I don't like writing graphical
front end code, the GUI largely is based on the
[NodeMCU PyFlasher](https://github.com/marcelstoer/nodemcu-pyflasher)
project.

The flashing process is done using the [esptool](https://github.com/espressif/esptool)
library by espressif.

## Installation

Es doesn't have to be installed, just double-click it and it'll start.
Check the [releases section](https://github.com/esphome/esphome-flasher/releases)
for downloads for your platform.

## Installation Using `pip`

If you want to install this application from `pip`:

- Install Python 3.x
- Install [wxPython 4.x](https://wxpython.org/) manually or run `pip3 install wxpython` (see also linux notes below)
- Install this project using `pip3 install esphomeflasher`
- Start the GUI using `esphomeflasher`. Alternatively, you can use the command line interface (
  type `esphomeflasher -h` for info)

## Build it yourself

If you want to build this application yourself you need to:

- Install Python 3.x
- Install [wxPython 4.x](https://wxpython.org/) manually or run `pip3 install wxpython`
- Download this project and run `pip3 install -e .` in the project's root.
- Start the GUI using `esphomeflasher`. Alternatively, you can use the command line interface (
  type `esphomeflasher -h` for info)


## Linux Notes

Installing wxpython for linux can be a bit challenging (especially when you don't want to install from source).
You can use the following command to install a wxpython suitable with your OS:

```bash
# Go to https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ and select the correct OS type
# here, we assume ubuntu 18.03 bionic
pip3 install -U \
    -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04 \
    wxPython
```

## License

[MIT](http://opensource.org/licenses/MIT) © Marcel Stör, Otto Winter

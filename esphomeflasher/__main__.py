from __future__ import print_function

import argparse
import sys
import time
from datetime import datetime

import esptool
import serial

from esphomeflasher import const
from esphomeflasher.common import (
    ESP32ChipInfo,
    EsphomeflasherError,
    chip_run_stub,
    configure_write_flash_args,
    detect_chip,
    detect_flash_size,
    read_chip_info,
)
from esphomeflasher.const import (
    ESP32_DEFAULT_BOOTLOADER_FORMAT,
    ESP32_DEFAULT_OTA_DATA,
    ESP32_DEFAULT_PARTITIONS,
)
from esphomeflasher.helpers import list_serial_ports


def parse_args(argv):
    parser = argparse.ArgumentParser(prog=f"esphomeflasher {const.__version__}")
    parser.add_argument("-p", "--port", help="Select the USB/COM port for uploading.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--esp8266", action="store_true")
    group.add_argument("--esp32", action="store_true")
    group.add_argument(
        "--upload-baud-rate",
        type=int,
        default=460800,
        help="Baud rate to upload with (not for logging)",
    )
    parser.add_argument(
        "--bootloader",
        help="(ESP32-only) The bootloader to flash.",
        default=ESP32_DEFAULT_BOOTLOADER_FORMAT,
    )
    parser.add_argument(
        "--partitions",
        help="(ESP32-only) The partitions to flash.",
        default=ESP32_DEFAULT_PARTITIONS,
    )
    parser.add_argument(
        "--otadata",
        help="(ESP32-only) The otadata file to flash.",
        default=ESP32_DEFAULT_OTA_DATA,
    )
    parser.add_argument(
        "--no-erase", help="Do not erase flash before flashing", action="store_true"
    )
    parser.add_argument("--show-logs", help="Only show logs", action="store_true")
    parser.add_argument("binary", help="The binary image to flash.")

    return parser.parse_args(argv[1:])


def select_port(args):
    if args.port is not None:
        print(f"Using '{args.port}' as serial port.")
        return args.port
    ports = list_serial_ports()
    if not ports:
        raise EsphomeflasherError("No serial port found!")
    if len(ports) != 1:
        print("Found more than one serial port:")
        for port, desc in ports:
            print(f" * {port} ({desc})")
        print("Please choose one with the --port argument.")
        raise EsphomeflasherError
    print(f"Auto-detected serial port: {ports[0][0]}")
    return ports[0][0]


def show_logs(serial_port):
    print("Showing logs:")
    with serial_port:
        while True:
            try:
                raw = serial_port.readline()
            except serial.SerialException:
                print("Serial port closed!")
                return
            text = raw.decode(errors="ignore")
            line = text.replace("\r", "").replace("\n", "")
            time_ = datetime.now().time().strftime("[%H:%M:%S]")
            message = time_ + line
            try:
                print(message)
            except UnicodeEncodeError:
                print(message.encode("ascii", "backslashreplace"))


def run_esphomeflasher(argv):
    args = parse_args(argv)
    port = select_port(args)

    if args.show_logs:
        serial_port = serial.Serial(port, baudrate=115200)
        show_logs(serial_port)
        return

    try:
        # pylint: disable=consider-using-with
        firmware = open(args.binary, "rb")
    except IOError as err:
        raise EsphomeflasherError(f"Error opening binary: {err}") from err
    chip = detect_chip(port, args.esp8266, args.esp32)
    info = read_chip_info(chip)

    print()
    print("Chip Info:")
    print(f" - Chip Family: {info.family}")
    print(f" - Chip Model: {info.model}")
    if isinstance(info, ESP32ChipInfo):
        print(f" - Number of Cores: {info.num_cores}")
        print(f" - Max CPU Frequency: {info.cpu_frequency}")
        print(f" - Has Bluetooth: {'YES' if info.has_bluetooth else 'NO'}")
        print(f" - Has Embedded Flash: {'YES' if info.has_embedded_flash else 'NO'}")
        print(
            f" - Has Factory-Calibrated ADC: {'YES' if info.has_factory_calibrated_adc else 'NO'}"
        )
    else:
        print(f" - Chip ID: {info.chip_id:08X}")

    print(f" - MAC Address: {info.mac}")

    stub_chip = chip_run_stub(chip)
    flash_size = None

    if args.upload_baud_rate != 115200:
        try:
            stub_chip.change_baud(args.upload_baud_rate)
        except esptool.FatalError as err:
            raise EsphomeflasherError(
                f"Error changing ESP upload baud rate: {err}"
            ) from err

        # Check if the higher baud rate works
        try:
            flash_size = detect_flash_size(stub_chip)
        except EsphomeflasherError:
            # Go back to old baud rate by recreating chip instance
            print(
                f"Chip does not support baud rate {args.upload_baud_rate}, changing to 115200"
            )
            # pylint: disable=protected-access
            stub_chip._port.close()
            chip = detect_chip(port, args.esp8266, args.esp32)
            stub_chip = chip_run_stub(chip)

    if flash_size is None:
        flash_size = detect_flash_size(stub_chip)

    print(f" - Flash Size: {flash_size}")

    mock_args = configure_write_flash_args(
        info, firmware, flash_size, args.bootloader, args.partitions, args.otadata
    )

    print(f" - Flash Mode: {mock_args.flash_mode}")
    print(f" - Flash Frequency: {mock_args.flash_freq.upper()}Hz")

    try:
        stub_chip.flash_set_parameters(esptool.flash_size_bytes(flash_size))
    except esptool.FatalError as err:
        raise EsphomeflasherError(f"Error setting flash parameters: {err}") from err

    if not args.no_erase:
        try:
            esptool.erase_flash(stub_chip, mock_args)
        except esptool.FatalError as err:
            raise EsphomeflasherError(f"Error while erasing flash: {err}") from err

    try:
        esptool.write_flash(stub_chip, mock_args)
    except esptool.FatalError as err:
        raise EsphomeflasherError(f"Error while writing flash: {err}") from err

    print("Hard Resetting...")
    stub_chip.hard_reset()

    print("Done! Flashing is complete!")
    print()

    if args.upload_baud_rate != 115200:
        # pylint: disable=protected-access
        stub_chip._port.baudrate = 115200
        time.sleep(0.05)  # get rid of crap sent during baud rate change
        # pylint: disable=protected-access
        stub_chip._port.flushInput()

    # pylint: disable=protected-access
    show_logs(stub_chip._port)


def main():
    try:
        if len(sys.argv) <= 1:
            from esphomeflasher import gui

            return gui.main() or 0
        return run_esphomeflasher(sys.argv) or 0
    except EsphomeflasherError as err:
        msg = str(err)
        if msg:
            print(msg)
        return 1
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())

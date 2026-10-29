#!/usr/bin/env python3
"""Cloud Cam BLE diagnostics. Original implementation; no firmware writes."""
import argparse
import hashlib
import json
import re
import time
import secrets
from pathlib import Path

BASE = "-0000-1000-8000-00805f9b34fb"
MANUFACTURER = "00002a29" + BASE
MODEL = "00002a24" + BASE
FIRMWARE = "00002a26" + BASE
HARDWARE = "00002a27" + BASE
CAPS = "6ab1baa0-05b9-11e6-9de4-0002a5d5c51b"
KEY_REQUEST = "790777c0-05b9-11e6-b047-0002a5d5c51b"
KEY_ACK = "a567a2e0-05b9-11e6-9840-0002a5d5c51b"
KEY_DATA = "d68e08a0-05b9-11e6-8635-0002a5d5c51b"
REG_REQUEST = "1223d920-6944-11e5-b3f7-0002a5d5c51b"
REG_ACK = "9228ace0-6944-11e5-98fa-0002a5d5c51b"
REG_STATE = "eb9eab2d-f9d9-4e16-a1b5-3afb99f70b36"
WIFI_REQUEST = "85150f00-6a3c-11e5-bf8c-0002a5d5c51b"
WIFI_ACK = "b98ee580-6a3c-11e5-8e85-0002a5d5c51b"
WIFI_STATE = "a04d2280-4ad4-11e5-a444-0002a5d5c51b"
SAVE_REQUEST = "6c5da720-4ad3-11e5-a50d-0002a5d5c51b"
SAVE_ACK = "8f12d880-4ad3-11e5-ba7f-0002a5d5c51b"
ALLOWED_WRITES = {KEY_REQUEST, REG_REQUEST, WIFI_REQUEST, SAVE_REQUEST}

def seal(key, payload):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(16)
    encrypted = AESGCM(key).encrypt(nonce, payload, None)
    fields = [(1, nonce), (2, encrypted[-16:]), (0, encrypted[:-16])]
    return b"".join(bytes([kind]) + len(value).to_bytes(2, "big") + value for kind, value in fields)

def wifi_config(path):
    target = Path(path)
    if target.stat().st_mode & 0o077:
        raise ValueError("Wi-Fi config must be private: chmod 600 FILE")
    cfg = json.loads(target.read_text())
    if not isinstance(cfg.get("ssid"), str) or not 1 <= len(cfg["ssid"].encode()) <= 32:
        raise ValueError("SSID must be 1-32 bytes")
    if cfg.get("keyMgmt") != "WPA_PSK" or not isinstance(cfg.get("psk"), str) or not 8 <= len(cfg["psk"]) <= 63:
        raise ValueError("This experiment requires WPA2-PSK with an 8-63 character passphrase")
    return {"ssid": cfg["ssid"], "psk": cfg["psk"], "keyMgmt": "WPA_PSK", "hidden": False, "priority": 1}

def parse_json(raw):
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value

def address(value):
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        raise argparse.ArgumentTypeError("Expected Bluetooth address AA:BB:CC:DD:EE:FF")
    return value.upper()

def run(args):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    root = "/org/bluez/" + args.adapter + "/dev_" + args.address.replace(":", "_")
    manager = dbus.Interface(bus.get_object("org.bluez", "/"),
                             "org.freedesktop.DBus.ObjectManager")
    if root not in manager.GetManagedObjects():
        adapter = dbus.Interface(bus.get_object("org.bluez", "/org/bluez/" + args.adapter),
                                 "org.bluez.Adapter1")
        adapter.StartDiscovery(timeout=10)
        try:
            deadline = time.monotonic() + 20
            while root not in manager.GetManagedObjects():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Camera did not advertise during 20-second discovery")
                time.sleep(0.25)
        finally:
            adapter.StopDiscovery(timeout=5)
    obj = bus.get_object("org.bluez", root)
    device = dbus.Interface(obj, "org.bluez.Device1")
    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    created_connection = not bool(props.Get("org.bluez.Device1", "Connected"))
    subscriptions = []
    report = {"stage": "connect", "firmware_modified": False}
    try:
        if created_connection:
            device.Connect(timeout=20)
        end = time.monotonic() + 15
        while not props.Get("org.bluez.Device1", "ServicesResolved"):
            if time.monotonic() > end:
                raise TimeoutError("GATT discovery timed out")
            time.sleep(0.2)
        objects = dbus.Interface(bus.get_object("org.bluez", "/"),
                                 "org.freedesktop.DBus.ObjectManager").GetManagedObjects()
        chars = {}
        services = []
        for path, interfaces in objects.items():
            if not str(path).startswith(root + "/"):
                continue
            if "org.bluez.GattService1" in interfaces:
                services.append(str(interfaces["org.bluez.GattService1"]["UUID"]))
            if "org.bluez.GattCharacteristic1" in interfaces:
                meta = interfaces["org.bluez.GattCharacteristic1"]
                chars[str(meta["UUID"])] = (str(path), meta)
        def interface(uuid):
            return dbus.Interface(bus.get_object("org.bluez", chars[uuid][0]),
                                  "org.bluez.GattCharacteristic1")
        def read(uuid):
            return bytes(interface(uuid).ReadValue({}, timeout=10))
        def write(uuid, payload):
            if uuid not in ALLOWED_WRITES:
                raise ValueError("Operation outside diagnostic write allowlist")
            interface(uuid).WriteValue(dbus.Array(payload, signature="y"),
                                      {"type": "request"}, timeout=10)
        notifications = {}
        def changed(iface, changed_props, invalidated, path=None):
            if iface == "org.bluez.GattCharacteristic1" and "Value" in changed_props:
                notifications[str(path)] = bytes(changed_props["Value"])
        bus.add_signal_receiver(changed, dbus_interface="org.freedesktop.DBus.Properties",
                                signal_name="PropertiesChanged", path_keyword="path")
        def subscribe(uuid):
            interface(uuid).StartNotify(timeout=10)
            subscriptions.append(uuid)
            context = GLib.MainContext.default()
            while context.pending():
                context.iteration(False)
            notifications.pop(chars[uuid][0], None)
        def response(uuid):
            context = GLib.MainContext.default()
            end = time.monotonic() + 10
            while time.monotonic() < end:
                while context.pending():
                    context.iteration(False)
                raw = notifications.get(chars[uuid][0])
                if raw:
                    return parse_json(raw)
                time.sleep(0.05)
            raw = read(uuid)
            if not raw.strip(b"\x00"):
                raise TimeoutError("No response notification; fallback value is empty")
            return parse_json(raw)
        report["stage"] = "identify"
        report["identity"] = {name: read(uuid).decode("utf-8", "replace") for name, uuid in
                              [("manufacturer", MANUFACTURER), ("model", MODEL),
                               ("firmware", FIRMWARE), ("hardware", HARDWARE)]}
        if report["identity"]["manufacturer"] != "Amazon" or report["identity"]["model"] != "A3SA7EC7BKYY63":
            raise ValueError("Device does not match the tested Cloud Cam family")
        report["services"] = sorted(services)
        report["characteristics"] = [{"uuid": u, "flags": list(map(str, m["Flags"])),
                                       "mtu": int(m.get("MTU", 0))} for u, (_, m) in sorted(chars.items())]
        report["capabilities"] = parse_json(read(CAPS))
        if args.refresh_registration:
            report["stage"] = "registration_refresh"
            subscribe(REG_ACK)
            write(REG_REQUEST, b"{}")
            report["registration_ack"] = response(REG_ACK)
            report["registration"] = parse_json(read(REG_STATE))
        if args.handshake or args.wifi_config:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization
            report["stage"] = "key_exchange"
            if 0 not in report["capabilities"].get("schemes", []):
                raise ValueError("Expected encryption scheme not offered")
            key = ec.generate_private_key(ec.SECP256R1())
            pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                         serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
            payload = json.dumps({"publicKey": pem, "scheme": 0}).encode()
            subscribe(KEY_ACK)
            report["request_bytes"] = len(payload)
            write(KEY_REQUEST, payload)
            report["key_request_accepted"] = True
            ack = response(KEY_ACK)
            report["key_ack"] = ack
            if ack.get("status") != 0:
                raise ValueError("Key exchange rejected")
            peer = serialization.load_pem_public_key(parse_json(read(KEY_DATA))["publicKey"].encode())
            session = hashlib.sha256(key.exchange(ec.ECDH(), peer)).digest()[:16]
            report["session_key_derived"] = len(session) == 16
            if args.wifi_config:
                report["stage"] = "save_wifi"
                cfg = wifi_config(args.wifi_config)
                subscribe(SAVE_ACK)
                write(SAVE_REQUEST, seal(session, json.dumps(cfg).encode()))
                report["wifi_write_accepted"] = True
                report["wifi_save_caution"] = "Configuration may already be applied even if acknowledgment times out; check AP/DHCP before retrying"
                report["save_wifi_ack"] = response(SAVE_ACK)
                if report["save_wifi_ack"].get("status") != 0:
                    raise ValueError("Camera rejected Wi-Fi configuration")
                report["network_configuration_saved"] = True
            report["stage"] = "wifi_status"
            subscribe(WIFI_ACK)
            write(WIFI_REQUEST, b"{}")
            report["wifi_ack"] = response(WIFI_ACK)
            raw = read(WIFI_STATE)
            try:
                wifi = parse_json(raw)
                report["wifi_status"] = {k: v for k, v in wifi.items() if k in ("state", "status")}
                report["wifi_fields"] = sorted(wifi.keys())
            except ValueError:
                report["wifi_status_encoding"] = "not plaintext JSON"
                report["wifi_status_bytes"] = len(raw)
        report["stage"] = "complete"
        return report, 0
    except Exception as error:
        report["error"] = str(error).replace(args.address, "<device>").replace(root, "<device-path>")
        return report, 1
    finally:
        for uuid in reversed(subscriptions):
            try:
                interface(uuid).StopNotify(timeout=5)
            except Exception:
                pass
        if created_connection:
            try:
                device.Disconnect(timeout=5)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True, type=address)
    parser.add_argument("--adapter", default="hci0", choices=["hci0", "hci1", "hci2"])
    parser.add_argument("--refresh-registration", action="store_true")
    parser.add_argument("--handshake", action="store_true")
    parser.add_argument("--wifi-config", help="Explicitly save a WPA2 network from a private JSON file")
    args = parser.parse_args()
    try:
        report, status = run(args)
    except Exception as error:
        report, status = {"stage": "connect", "error": str(error).replace(args.address, "<device>"), "firmware_modified": False}, 1
    print(json.dumps(report, indent=2))
    return status

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Cloud Cam BLE diagnostics. Original implementation; no firmware writes."""
import argparse
import hashlib
import json
import re
import time

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
ALLOWED_WRITES = {KEY_REQUEST, REG_REQUEST}

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
    bus = dbus.SystemBus()
    root = "/org/bluez/" + args.adapter + "/dev_" + args.address.replace(":", "_")
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
        def subscribe(uuid):
            interface(uuid).StartNotify(timeout=10)
            subscriptions.append(uuid)
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
            time.sleep(0.5)
            report["registration_ack"] = parse_json(read(REG_ACK))
            report["registration"] = parse_json(read(REG_STATE))
        if args.handshake:
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
            time.sleep(0.5)
            ack = parse_json(read(KEY_ACK))
            report["key_ack"] = ack
            if ack.get("status") != 0:
                raise ValueError("Key exchange rejected")
            peer = serialization.load_pem_public_key(parse_json(read(KEY_DATA))["publicKey"].encode())
            session = hashlib.sha256(key.exchange(ec.ECDH(), peer)).digest()[:16]
            report["session_key_derived"] = len(session) == 16
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
    args = parser.parse_args()
    try:
        report, status = run(args)
    except Exception as error:
        report, status = {"stage": "connect", "error": str(error).replace(args.address, "<device>"), "firmware_modified": False}, 1
    print(json.dumps(report, indent=2))
    return status

if __name__ == "__main__":
    raise SystemExit(main())

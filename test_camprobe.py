import argparse
import unittest
import camprobe

class InputTests(unittest.TestCase):
    def test_encrypted_wire_format_and_tamper_rejection(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        key = bytes(range(16)); payload = b'{"ssid":"test","psk":"not-a-real-secret"}'
        wire = camprobe.seal(key, payload); fields = {}; offset = 0
        while offset < len(wire):
            kind = wire[offset]; size = int.from_bytes(wire[offset+1:offset+3], "big")
            fields[kind] = wire[offset+3:offset+3+size]; offset += size + 3
        self.assertEqual(AESGCM(key).decrypt(fields[1], fields[0]+fields[2], None), payload)
        bad = bytes([fields[0][0] ^ 1]) + fields[0][1:] + fields[2]
        with self.assertRaises(InvalidTag):
            AESGCM(key).decrypt(fields[1], bad, None)
    def test_address_validation(self):
        self.assertEqual(camprobe.address("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")
        for value in ("", "../hci0", "AA:BB:CC:DD:EE", "GG:BB:CC:DD:EE:FF"):
            with self.assertRaises(argparse.ArgumentTypeError):
                camprobe.address(value)
    def test_uninitialized_state_is_not_registration_success(self):
        for raw in (b"\x00" * 64, b"[]", b"null", b"{broken"):
            with self.assertRaises((ValueError, UnicodeError)):
                camprobe.parse_json(raw)
    def test_state_zero_is_valid_data(self):
        self.assertEqual(camprobe.parse_json(b'{"state":0}'), {"state": 0})

if __name__ == "__main__":
    unittest.main()

import argparse
import unittest
import camprobe

class InputTests(unittest.TestCase):
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

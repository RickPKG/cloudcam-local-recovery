# Evidence ledger

Observed 2026-10-28 on an Amazon A3SA7EC7BKYY63 device using Linux BlueZ 5.72. Device identifiers and network secrets omitted.

| Test | Result | Limit |
|---|---|---|
| USB on two hosts | No camera data interface | Does not prove connector is power-only |
| BLE identity | Amazon / A3SA7EC7BKYY63 | Not a chipset identification |
| Initial registration refresh | status 0, state 0 | Later failed until fresh startup |
| Initial key exchange | ATT 0x80 at Execute Write | All three Prepare Write fragments acknowledged |
| After power cycle | key request accepted, notification status 0, session key derived | Not firmware access |
| Wi-Fi status request | ack status 0; payload status -12 | Not interpreted as a connection state |
| WPA2 configuration | write accepted, missing ack; AP association and DHCP independently succeeded | Treat BLE timeout as uncertain, not no change |
| Network isolation | Namespace contained only loopback + AP; routes to internet and home LAN unreachable | No household DNS/firewall changes |
| TLS test | arcus-uswest SNI seen; certificate_unknown alerts; some no-SNI connections ended EOF | No successful camera TLS handshake |
| TLS positive control | client trusting lab certificate completes handshake and receives 503 | Control traffic is not camera traffic |
| TLS negative control | ordinary client rejects unknown lab CA | Confirms listener observes failures |
| Local TCP services | No open ports among 22,23,80,443,554,8000,8080,8554 | Only these ports and this moment tested |

The test certificate had RSA-2048, SHA-256, validity 2000-2040, and SANs for dp-gw-na.amazon.com, piefs-pimms.amazonpmi.com, arcus-uswest.amazon.com. A self-signed certificate rejection alone cannot distinguish ordinary CA verification from hard-coded pinning. No forced registration operation was attempted. No firmware writes or factory reset performed.

Next evidence needed: valid active-registration request format from the original app/research; controlled TLS observation during that operation. A firmware dump is an alternative research input, not a proven requirement or an available feature of these tools.

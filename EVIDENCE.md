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

## Active registration experiment

Static inspection of the original Android APK `com.amazon.comppai` confirmed that the BLE registration operation serializes a RegistrationToken object with `token` (string) and `expiry` (long). The app invokes it with the literal expiry value 60000. The validator requires a nonempty token. The registration request and response are outside the SDK plaintext allowlist; the test uses the established encrypted session. Decompilation had 17 errors elsewhere; the inspected registration classes were readable. No APK or decompiled source is redistributed.

APK SHA256: `76bf658ea4af4f37c85c31db31d14d346b59ff6d102d07ee6e268d83966841a3`. APK signature verification succeeded, with unsigned META-INF metadata warnings. Signer SHA256: `2f19adeb284eb36f7f07786152b9a1d14b21653203ad0b04ebbf9c73ab6d7625`, matching the published APKMirror fingerprint.

An encrypted synthetic-token request was accepted by the initially unregistered camera. A new TLS client then used SNI `api.amazon.com`. The first certificate lacked that name, so its failure was not treated as evidence of pinning. A second run used CN api.amazon.com and a SAN including it; the device again sent certificate_unknown. Registration state was 0 both before and after the bounded probe. No camera handshake succeeded. No token from a real Amazon account was used.

These runs used a 10-second BLE response wait; a missing acknowledgment is inconclusive. The tool now defaults to the original app's 60-second response timeout. That longer timeout has not yet been re-tested on hardware. Certificate rejection itself was directly observed independently of the BLE timeout.

This rules out simple certificate substitution in the exercised path. It does not prove the published CVE is false or all possible recovery paths are closed. The exact verifier and remaining bootloader/firmware access are unresolved.

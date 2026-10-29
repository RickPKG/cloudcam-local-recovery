# Cloud Cam Local Recovery

An independent, MIT-licensed effort to recover owned, discontinued Amazon Cloud Cams for local Wi-Fi video.

**Research in progress. This is not a working replacement firmware or RTSP solution yet.**

## What works on our camera

- Bluetooth discovery: the camera advertises a `Pecan-...` name and provisioning service `31d84500-42e1-11e5-882e-0002a5d5c51b`.
- Read manufacturer `Amazon` and model identifier `A3SA7EC7BKYY63` directly over GATT.
- Enumerate its provisioning, Wi-Fi, registration, encryption and undocumented services.
- Read encryption capabilities: scheme 0.
- Complete P-256 key exchange after a fresh power-up, consuming the asynchronous success notification and deriving a session key.
- Save an encrypted WPA2 lab configuration. The camera joined the access point and obtained DHCP, independently confirming application despite a missing BLE acknowledgment.
- Observe the camera reaching our local TLS listener and rejecting its replacement certificate.
- One registration-refresh request returned status 0 and registration state 0. Later requests were rejected; do not assume that operation is reliable.

## Current blockers

Earlier secure-session requests failed with ATT `0x80` after the complete prepared write. After power cycling, writes succeeded; consuming asynchronous notifications fixed a separate response-reading bug. A reboot is an observed recovery on this unit, not a universal explanation for ATT 0x80.

The camera joins our isolated Wi-Fi network, but rejects the test TLS certificate for its observed cloud endpoints. Certificate acceptance during a distinct active registration flow is still untested. Wi-Fi is a milestone, not local video recovery.

Firmware/hardware revision strings are placeholders (`XXXXX1`, `X.X.X`). No firmware dump, certificate bypass, RTSP stream or ONVIF endpoint has been verified. See [EVIDENCE.md](EVIDENCE.md).

## Run the diagnostic

Linux with BlueZ, Python 3, `python3-dbus`, `python3-gi` and (only for the optional handshake/provisioning) `python3-cryptography`. On Debian/Ubuntu these are distribution packages. No pip dependencies are needed for identity reads.

```sh
bluetoothctl --timeout 20 scan le
python3 camprobe.py --address AA:BB:CC:DD:EE:FF
```

Use the address actually discovered next to the Pecan name. The device must be advertising; a stale BlueZ entry is not proof it is currently reachable.

Optional diagnostic operations:

```sh
python3 camprobe.py --address AA:BB:CC:DD:EE:FF --refresh-registration
python3 camprobe.py --address AA:BB:CC:DD:EE:FF --handshake
```

The default only reads attributes. Registration refresh and handshake flags write diagnostic requests. The handshake also refreshes Wi-Fi state. The separate `--wifi-config FILE` flag explicitly saves a WPA2 network and therefore changes camera configuration; use only when intended. The file must have mode 600 and contain `ssid`, `psk`, and `keyMgmt: "WPA_PSK"`. Credentials and session keys are never printed. The tool checks Amazon/model identity before writes. It does not flash, erase, reset, pair or trust the camera, and releases subscriptions/connections it creates.

A Wi-Fi save can take effect even when the acknowledgment times out. Check the access point and DHCP logs before retrying. This has occurred on our unit. [LAB.md](LAB.md) explains the isolated network and certificate experiment.

JSON output omits the camera address, serial number, host identity and cryptographic keys. Exit 0 means the requested diagnostic completed, **not that video recovery works**. Exit 1 means the diagnostic failed; `stage` and `error` explain where. Inspect reports before publishing because device-supplied errors may contain unexpected information.

## Certificate research

Amazon acknowledges a pairing-state SSL-pinning bypass in [CVE-2025-6031](https://aws.amazon.com/security/security-bulletins/AWS-2025-013/). The bulletin does not supply a recovery implementation. Its original researcher describes reconstructing the backend in [PackageWatch](https://www.silentrobots.com/presentations/).

The separate [cloudcam-rescue investigation](https://github.com/dvdcastro/cloudcam-rescue) documents Bluetooth UUIDs and experiments with a replacement backend. Its certificate failures do not establish that every pairing/registration path is closed. We have not reproduced the bypass ourselves.

## Recovery plan and success criteria

1. **Achieved on one unit:** secure Bluetooth session and encrypted Wi-Fi provisioning. Reproduce across other units.
2. Capture a controlled registration attempt on a separate camera test network.
3. Test the documented certificate behavior without changing household DNS or trust stores.
4. Reconstruct only the backend operations actually observed; obtain a local stream.
5. Verify moving video over Wi-Fi with upstream internet unavailable, then RTSP or Home Assistant playback.
6. If firmware access becomes necessary, identify the exact chips and obtain repeatable, matching readouts before changing firmware. Preserve per-device calibration and keys privately.

The undocumented Bluetooth service is not a proven firmware-update interface. This project deliberately has no guessed flash command.

## Contributions

Useful evidence: model-family identifiers, sanitized service inventories, packet-level failure location, and reproducible command sequences. Do not submit credentials, device private keys, full serials, home video or proprietary firmware. Open an issue with the command, adapter/BlueZ versions and redacted result. Distinguish observations from hypotheses.

## Provenance and license

The implementation here is original. Protocol identifiers and behavioral comparisons are credited to the linked research. No code or firmware from the other repository is redistributed: no license was present in the revision inspected (`15c62350fed7557269ecd749e557b930e3860663`). This project's code and original documentation are MIT licensed. Amazon is not affiliated with this project.

## Experimental registration probe

`--registration-probe` deliberately attempts registration with a fixed synthetic token after checking that the camera reports state 0. It can change temporary registration state; it is not a read-only command. Use only on an isolated lab network with TLS capture already running. It does not obtain an Amazon login token or claim successful registration. The original app schema and actual failed certificate experiment are documented in EVIDENCE.md. A timeout does not prove an operation had no effect.

The active-registration endpoint was tested with a matching test certificate and rejected it. Local video remains unavailable. The next research inputs are a verifiable firmware readout or a concrete reproducible certificate-bypass mechanism; a guessed flash or write to an undocumented BLE service is not included.

# Cloud Cam Local Recovery

An independent, MIT-licensed effort to recover owned, discontinued Amazon Cloud Cams for local Wi-Fi video.

**Research in progress. This is not a working replacement firmware or RTSP solution yet.**

## What works on our camera

- Bluetooth discovery: the camera advertises a `Pecan-...` name and provisioning service `31d84500-42e1-11e5-882e-0002a5d5c51b`.
- Read manufacturer `Amazon` and model identifier `A3SA7EC7BKYY63` directly over GATT.
- Enumerate its provisioning, Wi-Fi, registration, encryption and undocumented services.
- Read encryption capabilities: scheme 0.
- One registration-refresh request returned status 0 and registration state 0. Later requests were rejected; do not assume that operation is reliable.

## Current blockers

The secure-session request is rejected with ATT error `0x80`. A live Bluetooth trace shows all three Prepare Write fragments acknowledged, followed by rejection of Execute Write. MTU 82 alone does not explain this: another research project reports a working handshake at that MTU.

Firmware/hardware revision strings are placeholders (`XXXXX1`, `X.X.X`). They are not useful version numbers. No firmware dump, certificate bypass, RTSP stream or ONVIF endpoint has been verified on our unit.

## Run the diagnostic

Linux with BlueZ, Python 3, `python3-dbus` and (only for the optional handshake) `python3-cryptography`. On Debian/Ubuntu these are distribution packages. No pip dependencies are needed for identity reads.

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

The default only reads attributes. The two explicit flags write only a registration-state refresh or an ephemeral public-key exchange. The tool checks Amazon/model identity before those operations, does not change Wi-Fi credentials, and does not flash, erase, reset, pair or trust the camera. It releases its notification subscriptions and disconnects connections it created.

JSON output omits the camera address, serial number, host identity and cryptographic keys. Exit 0 means the requested diagnostic completed, **not that video recovery works**. Exit 1 means the diagnostic failed; `stage` and `error` explain where. Inspect reports before publishing because device-supplied errors may contain unexpected information.

## Certificate research

Amazon acknowledges a pairing-state SSL-pinning bypass in [CVE-2025-6031](https://aws.amazon.com/security/security-bulletins/AWS-2025-013/). The bulletin does not supply a recovery implementation. Its original researcher describes reconstructing the backend in [PackageWatch](https://www.silentrobots.com/presentations/).

The separate [cloudcam-rescue investigation](https://github.com/dvdcastro/cloudcam-rescue) documents Bluetooth UUIDs and experiments with a replacement backend. Its certificate failures do not establish that every pairing/registration path is closed. We have not reproduced the bypass ourselves.

## Recovery plan and success criteria

1. Reproduce a secure Bluetooth session and identify why commands are rejected.
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

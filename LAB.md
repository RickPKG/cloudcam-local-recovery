# Isolated certificate laboratory

The lab used a spare Linux Wi-Fi adapter supporting AP mode, an isolated network namespace, hostapd, dnsmasq and tls_probe.py. The host's main network interface remained outside the namespace. No veth, bridge, default route or forwarding link was added. Do not repurpose the adapter carrying your SSH session.

Prerequisites: Linux, root privileges for networking, an unused AP-capable Wi-Fi adapter, hostapd, dnsmasq, BlueZ, and Python dependencies listed in README. Inspect `iw dev`, `iw list`, current routes and active connections first.

## Network recipe

Choose a namespace name, a spare PHY/interface, and an unused subnet. The tested example used `cloudcam-lab`, `phy0`, `wlp99s0`, `10.77.0.1/24`; substitute your actual adapter. Disable NetworkManager management of only that unused interface, set it down, create the namespace, and move the PHY with `iw phy PHY set netns name NAMESPACE`. Inside the namespace enable loopback, assign the AP address and bring the interface up.

Run hostapd inside the namespace with WPA2-PSK, CCMP, an appropriate legal 2.4 GHz channel and a newly generated private passphrase. Keep the configuration mode 600. Do not use an open AP. Run dnsmasq in the same namespace bound exclusively to that interface, with a small DHCP pool, no upstream DNS and local DNS answers pointing to the listener. Do not change host-wide resolver settings.

Before provisioning, verify `ip -n NAMESPACE route` contains only the lab subnet and `ip -n NAMESPACE link` only loopback and AP. `ip netns exec NAMESPACE ip route get PUBLIC_IP` and the corresponding query for your home router must both fail as unreachable.

## TLS observation

Generate a temporary certificate and private key; keep the key outside your repository, mode 600. Choose SANs matching observed names. This is a test certificate, not an Amazon certificate.

```sh
sudo ip netns exec NAMESPACE python3 tls_probe.py --bind LAB_ADDRESS --cert CERT_FILE --key KEY_FILE
```

The probe records SNI, handshake outcomes and application-data length. It does not log request bodies, credentials or video and deliberately replies 503 instead of claiming registration succeeded. Validate it first with a client that trusts the test certificate (must succeed) and one that does not (must reject). Mark control timestamps so they are never mistaken for camera acceptance.

On the Bluetooth host, provide a mode-600 JSON file containing the lab SSID, passphrase and keyMgmt WPA_PSK, then run `camprobe.py --address CAMERA_ADDRESS --wifi-config FILE`. Keep that file out of Git. Check AP association and DHCP even if the BLE acknowledgment times out. Observe actual camera TLS results. Nothing in this procedure removes its certificate checks.

## Stop and restore

Stop only the lab's hostapd, dnsmasq and TLS processes. With the lab PHY still present, move it back to the host network namespace (`ip netns exec NAMESPACE iw phy PHY set netns 1`), then delete the now-empty lab namespace and restore NetworkManager management for that interface. Verify the original main route remains intact. Do not flush host firewall rules or delete other namespaces.

The camera retains the newly saved lab network after the lab stops. Preserve the private lab configuration for resuming; changing its saved network again is a separate provisioning action. This project has not implemented or verified network-entry deletion.

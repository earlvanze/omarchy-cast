# Omarchy Cast

An embedded LAN video-casting picker for the Omarchy Quickshell bar. Choose a DLNA receiver, browse local videos, and start playback without leaving the bar.

The popup and file browser use QML throughout. Network discovery and video preparation run in separate processes. High-bitrate or incompatible files are converted into a cached H.264/AAC playback copy; source files are preserved.

## Features

- Embedded device selector and video browser
- SSDP discovery, Samsung LAN discovery fallback, and manual IP lookup
- 1080p / 30 fps playback copies with a 5 Mbps video ceiling
- HTTP byte-range support for seeking
- Restart and stop shortcuts on the bar icon
- Receiver-specific media access and UFW rules

## Requirements

Tested with Omarchy 4.0.4, Quickshell 0.3.1, and Qt 6.11.2 using a top bar and a Samsung DLNA TV.

Required: Python 3.12+, FFmpeg, systemd user services, `notify-send`, UFW, and a working graphical Polkit authentication agent. The QML runtime needs Qt Quick Controls, Qt Quick Layouts, Qt Labs FolderListModel, and Quickshell's Hyprland module.

Playback uses **DLNA AVTransport**. Chromecast-only and AirPlay-only receivers are not supported. A Fire TV needs a compatible DLNA receiver app running. Other TV models have not been hardware-tested.

## Install

Clone the repository, then pass this computer's LAN address and discovery subnet:

```sh
git clone https://github.com/earlvanze/omarchy-cast.git
cd omarchy-cast
python3 install.py --host 192.168.1.10 --network 192.168.1.0/24
omarchy restart shell
```

Use `ip -4 address` to find your actual LAN address. A DHCP reservation is recommended. Re-run the installer if the host address changes.

The installer adds the cast icon beside the audio widget in `~/.config/omarchy/shell.json`, preserving the other modules. It keeps one pre-install copy as `shell.json.before-omarchy-cast`. It does not start playback or open firewall access during installation.

## Use

- **Left-click:** open the embedded picker, choose a receiver and video, then Cast.
- **Right-click:** restart the last video on the selected receiver.
- **Middle-click:** stop playback.

For a newly selected receiver, approve the local administrator prompt to add a UFW rule allowing that device to reach this computer on TCP **18794**. These rules persist. The HTTP server additionally restricts access to the currently selected receiver and the configured host address.

Discovery uses SSDP on the configured interface. The fallback probes Samsung's renderer port across the configured subnet, limited to at most 1024 addresses. Manual IP lookup supports several common renderer-description endpoints; receiver compatibility still depends on AVTransport support.

The video server starts on demand and stops after four hours. Optimized copies are cached under `~/.local/state/video-cast/`; they have no automatic eviction. This directory also contains local device selection and playback state. None of that runtime data belongs in a public repository.

## Files installed

| File | Purpose |
| --- | --- |
| `~/.config/omarchy/bar/modules/Cast.qml` | Embedded picker |
| `~/.local/bin/omarchy-cast` | Playback and encoding controller |
| `~/.local/state/video-cast/devices.py` | LAN discovery |
| `~/.local/state/video-cast/serve.py` | Selected-file HTTP server |
| `~/.config/systemd/user/video-cast.service` | On-demand server lifecycle |

## Troubleshooting

- **Receiver missing:** turn it on, enable its DLNA receiver, and scan again. Try its IP if multicast is filtered.
- **Playback does not start:** check `journalctl --user -u video-cast.service`, network reachability, and the receiver-specific firewall rule. The receiver must fetch `http://HOST:18794/tv.mp4`.
- **Encoding fails:** inspect `~/.local/state/video-cast/encode.log`.
- **Port occupied:** resolve the existing owner of TCP 18794; the server does not select another port.
- **Other bar positions:** popup placement is currently designed for the top bar.

## Remove

Remove the entry whose `id` is `cast` from the bar layout in `~/.config/omarchy/shell.json`, then restart the shell. Stop the media server with `systemctl --user stop video-cast.service`. Remove installed files listed above when no longer needed. Keep or delete cached copies separately according to your needs.

To remove a receiver's firewall rule:

```sh
sudo ufw delete allow from RECEIVER_IP to HOST_IP port 18794 proto tcp
```

## Checks

```sh
python3 -m unittest discover -s tests -v
```

The tests cover installation into a temporary home, preservation of unrelated bar settings, repeated installation, first-run state, and HTTP byte-range handling. Live validation additionally covered Samsung discovery, playback, and the embedded QML browser. No automated test turns on a TV or changes a firewall.

A sample GitHub Actions workflow is provided in `examples/github-actions-checks.yml`. To enable CI, copy it to `.github/workflows/checks.yml` using a GitHub credential with workflow permission.

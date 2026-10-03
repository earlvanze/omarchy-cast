#!/usr/bin/env python3
"""Install the cast widget into the current user's Omarchy configuration."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent

def install(home, host, network):
    home = home.resolve()
    address = ipaddress.IPv4Address(host)
    subnet = ipaddress.IPv4Network(network, strict=False)
    if address not in subnet or not address.is_private or address.is_loopback:
        raise ValueError('Choose a private LAN IPv4 address inside the scan subnet.')
    if subnet.num_addresses > 1024:
        raise ValueError('Use a discovery subnet of /22 or smaller (at most 1024 addresses).')
    if any(c in str(home) for c in ['"', "'", '\\', '\n', '\r', '%']):
        raise ValueError('The home path contains unsupported template characters.')
    config = home / '.config/omarchy/shell.json'
    settings = json.loads(config.read_text())
    right = settings['bar']['layout']['right']
    state = home / '.local/state/video-cast'
    modules = home / '.config/omarchy/bar/modules'
    bins = home / '.local/bin'
    units = home / '.config/systemd/user'
    scripts = home / '.local/share/nautilus/scripts'
    for directory in [state, modules, bins, units, scripts]:
        directory.mkdir(parents=True, exist_ok=True)
    destinations = {'Cast.qml': modules/'Cast.qml', 'omarchy-cast': bins/'omarchy-cast',
                    'devices.py': state/'devices.py', 'serve.py': state/'serve.py', 'cast-file': scripts/'Cast to TV'}
    for name, destination in destinations.items():
        text = (ROOT/'templates'/name).read_text()
        for key, value in {'@HOME@': str(home), '@LAN_IP@': str(address), '@LAN_NETWORK@': str(subnet)}.items():
            text = text.replace(key, value)
        destination.write_text(text)
    (bins/'omarchy-cast').chmod(0o755)
    (scripts/'Cast to TV').chmod(0o755)
    (units/'video-cast.service').write_text(
        '[Unit]\nDescription=LAN video casting\n[Service]\n'
        f'ExecStart=/usr/bin/python3 "{state}/serve.py"\nRuntimeMaxSec=4h\n')
    module = {'id': 'cast', 'type': 'qml', 'source': str(modules/'Cast.qml')}
    found = next((i for i, entry in enumerate(right) if entry['id'] == 'cast'), None)
    if found is None:
        index = next((i for i, entry in enumerate(right) if entry['id'] == 'omarchy.audio'), len(right))
        right.insert(index, module)
    else:
        right[found] = module
    # One recovery point, not a growing series of duplicate backups.
    recovery = config.with_name('shell.json.before-omarchy-cast')
    if not recovery.exists():
        shutil.copy2(config, recovery)
    config.write_text(json.dumps(settings, indent=2)+'\n')
    return destinations

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='This computer’s LAN IPv4 address')
    parser.add_argument('--network', required=True, help='LAN discovery subnet, e.g. 192.168.1.0/24')
    args = parser.parse_args()
    required = ['ffmpeg', 'ffprobe', 'systemctl', 'notify-send', 'pkexec', 'ufw', 'quickshell']
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        parser.error('Missing dependencies: '+', '.join(missing))
    install(Path.home(), args.host, args.network)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    print('Installed. Run: omarchy restart shell')
    print('New receiver selections request administrator authentication for a receiver-specific UFW rule.')

if __name__ == '__main__':
    main()

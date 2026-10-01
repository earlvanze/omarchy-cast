import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

installer = load('installer', ROOT/'install.py')
server = load('server', ROOT/'templates/serve.py')

class InstallTests(unittest.TestCase):
    def test_install_preserves_bar_and_supports_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = home/'.config/omarchy/shell.json'
            path.parent.mkdir(parents=True)
            original = {'idle': {'lock': 500}, 'bar': {'layout': {'right': [{'id': 'omarchy.audio'}]}}}
            path.write_text(json.dumps(original))
            for _ in range(2):
                files = installer.install(home, '192.168.1.10', '192.168.1.0/24')
            config = json.loads(path.read_text())
            self.assertEqual(config['idle'], original['idle'])
            self.assertEqual([x['id'] for x in config['bar']['layout']['right']], ['cast','omarchy.audio'])
            self.assertEqual(json.loads(path.with_name('shell.json.before-omarchy-cast').read_text()), original)
            for file in files.values():
                self.assertNotIn('@HOME@', file.read_text())
                self.assertNotIn('@LAN_', file.read_text())
                if file.suffix != '.qml':
                    compile(file.read_text(), str(file), 'exec')
            # Import without touching the real home or requiring saved target state.
            from unittest.mock import patch
            from importlib.machinery import SourceFileLoader
            with patch('pathlib.Path.home', return_value=home):
                loader = SourceFileLoader('controller', str(files['omarchy-cast']))
                spec = importlib.util.spec_from_loader('controller', loader)
                mod = importlib.util.module_from_spec(spec)
                loader.exec_module(mod)
                self.assertIsNone(mod.TARGET)
                with self.assertRaisesRegex(RuntimeError, 'Choose a receiver'):
                    mod.soap('GetTransportInfo')

    def test_rejects_wrong_subnet(self):
        with self.assertRaises(ValueError):
            installer.install(Path('/unused'), '192.168.1.10', '10.0.0.0/24')

class RangeTests(unittest.TestCase):
    def test_valid_ranges(self):
        for header, expected in [(None,(0,99)),('bytes=0-9',(0,9)),('bytes=90-',(90,99)),('bytes=-10',(90,99)),('bytes=90-200',(90,99))]:
            self.assertEqual(server.byte_range(header,100),expected)

    def test_invalid_ranges(self):
        for header in ['bytes=100-', 'bytes=20-10', 'bytes=-0', 'bytes=-', 'bytes=0-1,5-6', 'bad']:
            with self.assertRaises(ValueError):
                server.byte_range(header,100)

if __name__ == '__main__':
    unittest.main()

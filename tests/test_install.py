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

class PlaybackTests(unittest.TestCase):
    def setUp(self):
        from importlib.machinery import SourceFileLoader
        from unittest.mock import patch
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with patch('pathlib.Path.home', return_value=Path(self.tmp.name)):
            loader = SourceFileLoader('playback_controller', str(ROOT/'templates/omarchy-cast'))
            spec = importlib.util.spec_from_loader(loader.name, loader)
            self.mod = importlib.util.module_from_spec(spec)
            loader.exec_module(self.mod)

    def test_seek_clamps_to_media_duration(self):
        from unittest.mock import patch
        with patch.object(self.mod, 'soap', return_value=b'<r><RelTime>00:00:55</RelTime><TrackDuration>00:01:00</TrackDuration></r>') as soap:
            self.mod.playback('skip', 10)
            self.assertEqual(soap.call_args.args, ('Seek',))
            self.assertEqual(soap.call_args.kwargs, {'Unit':'REL_TIME','Target':'00:00:59'})

    def test_toggle_reads_remote_state(self):
        from unittest.mock import patch
        with patch.object(self.mod, 'soap', return_value=b'<r><CurrentTransportState>PLAYING</CurrentTransportState></r>') as soap:
            self.mod.playback('toggle')
            self.assertEqual(soap.call_args.args, ('Pause',))

    def test_volume_uses_rendering_service_and_clamps(self):
        from unittest.mock import patch
        with patch.object(self.mod, 'soap') as soap:
            self.mod.playback('volume', 200)
            soap.assert_called_once_with('SetVolume', _render=True, Channel='Master', DesiredVolume=100)

    def test_fractional_tv_timestamp(self):
        self.assertEqual(self.mod.seconds('0:01:02.500'), 62)
        self.assertEqual(self.mod.timestamp(62), '00:01:02')

class FaststartTests(unittest.TestCase):
    setUp = PlaybackTests.setUp
    def test_index_must_precede_media(self):
        import struct
        path = Path(self.tmp.name)/'example.mp4'
        def atom(kind): return struct.pack('>I4s',8,kind)
        path.write_bytes(atom(b'ftyp')+atom(b'mdat')+atom(b'moov'))
        self.assertFalse(self.mod.faststart(path))
        path.write_bytes(atom(b'ftyp')+atom(b'moov')+atom(b'mdat'))
        self.assertTrue(self.mod.faststart(path))
        path.write_bytes(b'broken')
        self.assertFalse(self.mod.faststart(path))

if __name__ == '__main__':
    unittest.main()

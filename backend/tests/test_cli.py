from argparse import Namespace
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('omnidev_cli', Path(__file__).resolve().parents[2] / 'cli' / 'main.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_memory_subcommands_dispatch(capsys):
    class Client:
        def get_session_memory(self, key):
            return {'key': key, 'value': 'saved'}

        def set_session_memory(self, key, value, data):
            return {'key': key, 'value': value, 'data': data}

    assert cli.cmd_memory_session(Client(), Namespace(subaction='set', key='k', value='v', data=None)) == 0
    assert '"value": "v"' in capsys.readouterr().out
    assert cli.cmd_memory_session(Client(), Namespace(subaction='get', key='k')) == 0
    assert '"value": "saved"' in capsys.readouterr().out
    assert cli.cmd_memory_session(Client(), Namespace(subaction='get', key=None)) == 1

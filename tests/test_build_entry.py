"""Cache orchestration checks without compiler builds or external tools."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('make_data',Path(__file__).resolve().parents[1]/'make_data.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)

class EntryTests(unittest.TestCase):
    def test_unchanged_inputs_skip_every_build_command(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cache=root/'cache';dist=root/'dist';cache.mkdir();dist.mkdir()
            archive=dist/'prepared-layouts.tar.gz';archive.write_bytes(b'prepared')
            identity={'recipe':'same'}
            (cache/'build-receipt.json').write_text(json.dumps({'inputs':identity,'archive_sha256':entry.sha(archive)}))
            with patch.object(entry,'CACHE',cache), patch.object(entry,'DIST',dist), patch.object(entry,'input_identity',return_value=identity), patch.object(entry,'compiler_current',return_value=True), patch.object(entry,'script',side_effect=AssertionError('unexpected build')):
                entry.build(SimpleNamespace())

    def test_profile_changes_do_not_invalidate_compiler_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);tools=root/'tools';compiler=root/'compiler';tools.mkdir();compiler.mkdir()
            inputs={}
            for name in ('engine.cpp','CMakeLists.txt','toolchain.lock.json','build.py'):
                (tools/name).write_bytes(name.encode());inputs[name]=entry.sha(tools/name)
            inputs['profiles/ios-catalog.json']='historical profile checksum'
            (compiler/'layout-engine').write_bytes(b'compiler')
            (compiler/'toolchain-provenance.json').write_text(json.dumps({'inputs':inputs,'artifacts':{'layout-engine':{'sha256':entry.sha(compiler/'layout-engine')}}}))
            with patch.object(entry,'TOOLS',tools): self.assertTrue(entry.compiler_current(compiler))

if __name__=='__main__':unittest.main()

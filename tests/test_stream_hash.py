import hashlib, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from llm_security_lab.backends import sha256_file
class StreamHashTests(unittest.TestCase):
    def test_large_and_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"weight"
            for payload in (b"",b"abc"*800000):
                path.write_bytes(payload)
                with patch.object(Path,"read_bytes",side_effect=AssertionError("whole file read")):
                    self.assertEqual(sha256_file(path),hashlib.sha256(payload).hexdigest())

import gzip
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from export_stock_ikconfig import extract_stock_ikconfig, main


def make_stock_boot(config: bytes) -> bytes:
    image = (b"ARM64 mocked prefix" + b"IKCFG_ST"
             + gzip.compress(config, mtime=0) + b"IKCFG_ED")
    kernel = gzip.compress(image, mtime=0)
    stock = bytearray(4096 + len(kernel))
    stock[:8] = b"ANDROID!"
    struct.pack_into("<8I", stock, 8, len(kernel), 0, 1, 0, 0, 0, 0, 4096)
    struct.pack_into("<I", stock, 40, 2)
    struct.pack_into("<IQI", stock, 1632, 0, 0, 1660)
    struct.pack_into("<IQ", stock, 1648, 0, 0)
    stock[4096:] = kernel
    return bytes(stock)


class TestExportStockIKConfig(unittest.TestCase):
    def test_extracts_exact_original_config(self):
        config = b"# Linux/arm64 4.14 config\nCONFIG_MODVERSIONS=y\n"
        self.assertEqual(extract_stock_ikconfig(make_stock_boot(config)), config)

    def test_rejects_missing_boot_magic_and_broken_kernel(self):
        with self.assertRaisesRegex(ValueError, "Android boot header"):
            extract_stock_ikconfig(b"not an android image")
        malformed = bytearray(make_stock_boot(b"CONFIG_MODVERSIONS=y\n"))
        malformed[4096:4100] = b"oops"
        with self.assertRaisesRegex(ValueError, "not gzip"):
            extract_stock_ikconfig(bytes(malformed))

    def test_cli_exports_only_when_hash_matches_and_no_overwrite(self):
        config = b"# stock config\nCONFIG_KPROBES=n\n"
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            boot = directory / "boot.img"
            output = directory / "stock.config"
            boot.write_bytes(make_stock_boot(config))
            good = hashlib.sha256(config).hexdigest()
            self.assertEqual(main(["--boot", str(boot), "--output", str(output),
                                   "--expect-config-sha256", good]), 0)
            self.assertEqual(output.read_bytes(), config)
            self.assertEqual(main(["--boot", str(boot), "--output", str(output)]), 1)
            other = directory / "bad.config"
            self.assertEqual(main(["--boot", str(boot), "--output", str(other),
                                   "--expect-config-sha256", "0" * 64]), 1)
            self.assertFalse(other.exists())


if __name__ == "__main__":
    unittest.main()

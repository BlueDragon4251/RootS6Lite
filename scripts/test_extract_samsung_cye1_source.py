import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from extract_samsung_cye1_source import (
    CYE1_EXPECTED_FILES,
    apply_cye1_overlay,
    normalized_name,
    unpack_base,
)


def tar_with_files(files: dict[str, bytes], links: dict[str, str] | None = None) -> tarfile.TarFile:
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as tar:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            entry.mode = 0o644
            tar.addfile(entry, io.BytesIO(content))
        for name, target in (links or {}).items():
            entry = tarfile.TarInfo(name)
            entry.type = tarfile.SYMTYPE
            entry.linkname = target
            tar.addfile(entry)
    data.seek(0)
    return tarfile.open(fileobj=data, mode="r:")


class Cye1ExtractionTests(unittest.TestCase):
    def test_normalized_safe_and_unsafe_paths(self):
        self.assertEqual(normalized_name("./drivers/Kconfig"), "drivers/Kconfig")
        self.assertEqual(normalized_name("./"), "")
        for name in ("/etc/passwd", "../passwd", "foo/../bar", "foo\\bar"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                normalized_name(name)

    def test_base_unpacks_regular_files_and_internal_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with tar_with_files({"./a.txt": b"test"}, {"./b.txt": "a.txt"}) as tar:
                stats = unpack_base(tar, root)
            self.assertEqual((root / "b.txt").read_bytes(), b"test")
            self.assertEqual(stats, {"base_regular_files": 1, "base_symlinks": 1})

    def test_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tar_with_files({}, {"./bad": "../../outside"}) as tar:
                with self.assertRaisesRegex(ValueError, "Symlink escapes"):
                    unpack_base(tar, Path(tmp))

    def test_overlay_can_create_wlan_defconfig_and_replace_audio_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {name: name.encode() for name in CYE1_EXPECTED_FILES}
            with tar_with_files(files) as tar:
                hashes = apply_cye1_overlay(tar, root)
            self.assertEqual(set(hashes), CYE1_EXPECTED_FILES)
            self.assertEqual((root / "arch/arm64/configs/gta4xlvewifi_eur_open_defconfig").read_bytes(),
                             b"Kernel/arch/arm64/configs/gta4xlvewifi_eur_open_defconfig")

    def test_overlay_refuses_unknown_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            with tar_with_files({"Kernel/extra.c": b"bad"}) as tar:
                with self.assertRaisesRegex(ValueError, "Unexpected CYE1 overlay entry"):
                    apply_cye1_overlay(tar, Path(tmp))


if __name__ == "__main__":
    unittest.main()

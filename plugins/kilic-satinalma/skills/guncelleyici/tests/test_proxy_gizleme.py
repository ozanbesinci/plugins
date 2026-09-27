"""Kurulum yapmadan gerçek hata/rapor yollarında proxy kimliğini sınar."""
import contextlib
import datetime
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

KAYNAK = Path(__file__).resolve().parents[3] / "skills/guncelleyici/scripts"


def yukle(ad):
    spec = importlib.util.spec_from_file_location(ad.replace("-", "_"), KAYNAK / f"{ad}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ProxyTest(unittest.TestCase):
    def test_hata_ekran_rapor_json(self):
        for uzunluk in (1, 120):
            proxy = "http://deneme:" + "GIZLI_PAROLA_" * uzunluk + "@proxy.invalid:yanlis"
            hata = f"ERROR: Invalid proxy URL {proxy}\n"
            for ad in ("kurulum-testi", "python-paket-kur"):
                with self.subTest(betik=ad, uzunluk=uzunluk), tempfile.TemporaryDirectory(prefix="pg-proxy-test-") as gecici:
                    mod = yukle(ad)
                    ekran = io.StringIO()
                    mod.DURUM_KLASORU = gecici
                    rapor = Path(gecici) / "rapor.txt"
                    rapor.write_text("", encoding="utf-8")
                    sonuc = subprocess.CompletedProcess([], 1, "", hata)
                    with contextlib.redirect_stdout(ekran), patch.object(mod, "sistem_proxy", return_value=proxy), patch.object(mod.subprocess, "run", return_value=sonuc) as calistir:
                        if ad == "kurulum-testi":
                            self.assertFalse(mod.kutuphaneleri_kur())
                            rapor = Path(mod.rapor_yaz(gecici, datetime.datetime.now(), None))
                        else:
                            with patch.object(mod, "kurulu_surum", return_value=None), patch.object(mod, "pypi_en_yeni", return_value=None), patch.object(sys, "argv", [ad, "duckdb", "--rapor", str(rapor)]):
                                with self.assertRaises(SystemExit) as cikis:
                                    mod.main()
                                self.assertEqual(cikis.exception.code, 0)
                            veri = json.loads((Path(gecici) / "duckdb-kur-sonuc.json").read_text(encoding="utf-8"))
                            self.assertEqual(veri["durum"], "BASARISIZ")
                        komut = calistir.call_args.args[0]
                        self.assertEqual(komut[komut.index("--proxy") + 1], proxy)
                    metin = ekran.getvalue() + rapor.read_text(encoding="utf-8-sig") + json.dumps(mod.sonuclar)
                    if ad == "python-paket-kur":
                        metin += json.dumps(veri)
                    for yasak in ("GIZLI", "PAROLA", "deneme:"):
                        self.assertNotIn(yasak, metin)
                    self.assertIn("http://***@proxy.invalid:yanlis", metin)


if __name__ == "__main__":
    unittest.main()

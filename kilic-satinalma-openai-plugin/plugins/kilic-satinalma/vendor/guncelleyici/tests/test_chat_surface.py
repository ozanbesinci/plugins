"""Regression guards for the end-user chat-only surface.

Normal purchasing staff use the skill from ChatGPT Desktop Work/Codex. Shell
commands are agent-internal; only developer/IT acceptance may expose test commands.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def text(path):
    return path.read_text(encoding="utf-8-sig")

class ChatOnlySurfaceTests(unittest.TestCase):
    def test_skill_forbids_end_user_terminal_handoff(self):
        skill=text(ROOT/"SKILL.md")
        self.assertIn("Son kullanıcı yüzeyi yalnız **ChatGPT Desktop Work veya Codex sohbetidir**", skill)
        self.assertIn("Kullanıcıdan\nTerminal/PowerShell açmasını", skill)
        self.assertIn("Work/Codex bunları kendi yerel shell/terminal aracıyla arka planda çalıştırır", skill)
        self.assertIn("yerel yürütme\nkullanılamıyor", skill)

    def test_powerbi_deferred_binding_returns_to_chat_not_terminal(self):
        pbi=text(ROOT/"scripts"/"powerbi-mcp-kur.ps1")
        self.assertIn("sohbette bağlamayı yeniden isteyin", pbi)
        self.assertIn("Work/Codex bakım adımını yerel olarak çalıştırır", pbi)
        self.assertNotIn("-BindOnly bakım komutunu çalıştırın", pbi)

    def test_reference_marks_terminal_commands_as_internal_or_it_only(self):
        program=text(ROOT/"references"/"program-kurulumu.md")
        acceptance=text(ROOT/"references"/"kabul-ve-kurtarma.md")
        self.assertIn("Work/Codex yerel\nyürütme aracı", program)
        self.assertIn("Son kullanıcıdan PowerShell veya\nterminal açması istenmez", program)
        self.assertIn("Yalnız geliştirici/BT kabulü", acceptance)
        self.assertIn("normal personel\n> kullanım akışının parçası değildir", acceptance)

if __name__ == "__main__":
    unittest.main()

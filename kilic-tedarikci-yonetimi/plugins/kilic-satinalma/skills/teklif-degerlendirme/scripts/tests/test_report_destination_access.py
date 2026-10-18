"""Published stages inherit destination access on Windows, without ACL edits."""
import os
from pathlib import Path
import tempfile
import unittest
from report_delivery import _new_stage,_publish_directory

class DestinationAccessTests(unittest.TestCase):
    def test_unique_stages_publish_with_destination_inheritance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            a=_new_stage(root,'.stage-');b=_new_stage(root,'.stage-')
            self.assertNotEqual(a,b)
            (a/'report.txt').write_text('complete',encoding='utf-8')
            target=root/'delivered';_publish_directory(a,target)
            self.assertEqual((target/'report.txt').read_text(encoding='utf-8'),'complete')
            with self.assertRaises(FileExistsError):_publish_directory(b,target)
            self.assertTrue(b.is_dir())
            if os.name=='nt':
                import win32security
                for path in (target,target/'report.txt',b):
                    sd=win32security.GetFileSecurity(str(path),win32security.DACL_SECURITY_INFORMATION)
                    control,_=sd.GetSecurityDescriptorControl()
                    self.assertFalse(control & win32security.SE_DACL_PROTECTED)

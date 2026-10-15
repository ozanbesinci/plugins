import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_context as fixtures

ROOT=Path(__file__).resolve().parents[1]


class OperationalReadOnlyCLITests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def cli(self,*arguments):
        command=[sys.executable,str(ROOT/'scripts/contract_cli.py'),'--workspace',str(self.store.root),
                 '--output-root',str(self.store.output_root),'--source-root',str(self.sources),*arguments]
        run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(0,run.returncode,run.stdout+run.stderr)
        value=json.loads(run.stdout)
        self.assertEqual('READ_ONLY',value['retry_safety']);self.assertEqual('NOT_GRANTED',value['business_acceptance'])
        return value['result']

    def test_capacity_cli_reports_real_case_without_semantic_revision_mutation(self):
        before=self.rev();result=self.cli('capacity','--case-id',self.case)
        self.assertEqual('capacity-1.0',result['schema_version']);self.assertEqual(before,self.rev())

    def test_explicit_source_role_cli_does_not_promote_historical_reference(self):
        self.path.write_bytes(self.path.read_bytes()+b'new-version-trailer')
        child=self.store.ingest(self.case,self.doc,self.path,expected_revision=self.rev(),parent_version_id=self.version)['version_id']
        before=self.rev()
        result=self.cli('version-compare','--case-id',self.case,'--reference-version-id',self.version,'--current-target-version-id',child)
        self.assertEqual('REFERENCE_ONLY',result['reference']['role']);self.assertFalse(result['critical_analysis_allowed'])
        self.assertEqual(before,self.rev())

    def test_output_inspector_cli_is_empty_and_never_executes_an_action(self):
        before=self.rev();result=self.cli('output-inspect','--case-id',self.case)
        self.assertEqual([],result['operations']);self.assertEqual('NONE',result['recovery_action'])
        self.assertFalse(result['production_ready']);self.assertEqual(before,self.rev())

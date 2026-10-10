import contextlib
import io
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import error_log as log


class ErrorLogging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ,{'LOCALAPPDATA':str(self.root)})
        self.env.start()
        self.count = log._COUNT
        log._COUNT = 0

    def tearDown(self):
        log._COUNT = self.count
        self.env.stop()
        self.temp.cleanup()

    def events(self):
        return [json.loads(line) for path in self.root.rglob('*.jsonl') for line in path.read_text(encoding='utf-8').splitlines()]

    def test_error_metadata_excludes_private_text_arguments_and_paths(self):
        @log.log_failures('test.boundary')
        def bad(secret):
            raise ValueError(secret)
        secret='PRIVATE document account C:\\Customer\\quote.pdf'
        with self.assertRaises(ValueError) as caught:
            bad(secret)
        self.assertEqual(str(caught.exception),secret)
        event = self.events()[0]
        text=json.dumps(event)
        self.assertNotIn('PRIVATE',text)
        self.assertNotIn(str(self.root),text)
        self.assertNotIn('quote.pdf',text)
        self.assertEqual(event['exception_type'],'ValueError')
        self.assertEqual(event['frames'][-1]['function'],'bad')
        self.assertLessEqual(len(event['frames']),5)

    def test_success_and_normal_missing_information_are_not_errors(self):
        for status in ('READY','PASS','VERIFIED','PRELIMINARY','PRELIMINARY_ONLY','UNVERIFIED','NEEDS_LLM_RESPONSE','KISMI','BILGI_GEREKLI'):
            value={'status':status,'private':'document contents'}
            self.assertIs(log.log_failures('test.boundary')(lambda:value)(),value)
        self.assertEqual(self.events(),[])

    def test_explicit_failures_log_without_changing_result_or_stdout(self):
        for status in ('FAIL','BLOCKED','BLOCKED_ENVIRONMENT','ERROR'):
            value={'status':status,'blocking_reasons':['PRIVATE']}
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
                self.assertIs(log.log_failures('test.boundary')(lambda:value)(),value)
            self.assertEqual(stream.getvalue(),'')
        self.assertEqual(len(self.events()),4)
        self.assertNotIn('PRIVATE',json.dumps(self.events()))

    def test_logger_failure_preserves_original_exception_and_return_value(self):
        file=self.root/'file';file.write_text('keep',encoding='utf-8')
        os.environ['LOCALAPPDATA']=str(file)
        error=ValueError('original')
        @log.log_failures('test.boundary')
        def fail():
            raise error
        with self.assertRaises(ValueError) as caught:
            fail()
        self.assertIs(caught.exception,error)
        value={'status':'BLOCKED'}
        self.assertIs(log.log_failures('test.boundary')(lambda:value)(),value)
        self.assertEqual(file.read_text(encoding='utf-8'),'keep')

    def test_missing_localappdata_disables_logging(self):
        os.environ.pop('LOCALAPPDATA',None)
        self.assertFalse(log.log_error('test.boundary',status='ERROR'))
        self.assertEqual(self.events(),[])

    def test_missing_package_metadata_keeps_unknown_event(self):
        with patch.object(Path,'read_text',side_effect=OSError('PRIVATE')):
            self.assertTrue(log.log_error('test.boundary',status='ERROR'))
        self.assertEqual(self.events()[0]['component_version'],'UNKNOWN')
        self.assertEqual(self.events()[0]['plugin_version'],'UNKNOWN')

    def test_busy_lock_drops_event_without_waiting(self):
        log._LOCK.acquire()
        try:
            self.assertFalse(log.log_error('test.boundary',status='ERROR'))
        finally:
            log._LOCK.release()
        self.assertEqual(self.events(),[])

    def test_event_limit_and_file_limit_preserve_existing_logs(self):
        for _ in range(log.MAX_EVENTS):
            self.assertTrue(log.log_error('test.boundary',status='ERROR'))
        self.assertFalse(log.log_error('test.boundary',status='ERROR'))
        self.assertEqual(len(self.events()),log.MAX_EVENTS)
        log._COUNT=0
        path=next(self.root.rglob('*.jsonl'))
        sentinel=b'X'*log.MAX_BYTES
        path.write_bytes(sentinel)
        self.assertFalse(log.log_error('test.boundary',status='ERROR'))
        self.assertEqual(path.read_bytes(),sentinel)

    def test_metadata_rejects_untrusted_tokens_without_str_coercion(self):
        class Private:
            def __str__(self):
                raise AssertionError('must not inspect caller object')
        self.assertTrue(log.log_error(Private(),status='PRIVATE contents / path'))
        event=self.events()[0]
        self.assertEqual(event['operation'],'UNKNOWN')
        self.assertEqual(event['status'],'UNKNOWN')

    def test_real_environment_boundary_and_cli_response_are_preserved(self):
        import environment_check as env
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.object(env,'check_requirements',return_value={'ok':False}),patch.object(env,'check_duckdb_pdf',return_value={}),patch.object(env,'missing_component_list',return_value=[]):
            with patch.object(sys,'argv',['environment_check.py','--strict']),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                exit_code=env.main()
        result=json.loads(stdout.getvalue())
        self.assertEqual(exit_code,3)
        self.assertEqual(result['status'],'BLOCKED_ENVIRONMENT')
        self.assertEqual(stderr.getvalue().strip(),result['user_message'])
        self.assertEqual(self.events()[0]['operation'],'environment_check.check')


if __name__=='__main__':
    unittest.main()

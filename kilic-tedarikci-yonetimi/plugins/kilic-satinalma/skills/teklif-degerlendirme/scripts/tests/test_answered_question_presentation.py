"""Completed unknown replies suppress presentation, never commercial QA issues."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from db import connect, init_db
from question_waits import active, record_answer, register
from user_question_gate import questions, waiting


class AnsweredQuestionPresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / 'run'
        init_db(self.run)

    def tearDown(self):
        self.temp.cleanup()

    def issue(self, issue_id='q-1', text='Firmadan ödeme açıklaması alındı mı?'):
        con = connect(self.run)
        try:
            con.execute('''INSERT INTO open_issues
                (issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                [issue_id,'IDARE','high','payment_comparability',text,'[]','[]','open',issue_id])
            con.commit()
        finally:
            con.close()

    def answer(self, q, text='Henüz açıklama alınmadı', sufficient=True, **extra):
        register(self.run, q)
        return record_answer(self.run, q['issue_id'], q['scope_sha256'], text,
                             sufficient=sufficient, response_sha256='a'*64, **extra)

    def test_complete_unknown_not_reasked_and_business_issue_stays_open(self):
        self.issue()
        q = questions(self.run)['questions'][0]
        self.assertTrue(self.answer(q)['resumed'])
        self.assertIsNone(waiting(self.run))
        self.assertEqual(questions(self.run)['open_question_count'], 0)
        self.assertEqual(active(self.run), [])
        con = connect(self.run)
        try:
            self.assertEqual(con.execute('SELECT status FROM open_issues').fetchone()[0], 'open')
            self.assertEqual(con.execute('SELECT count(*) FROM facts').fetchone()[0], 0)
        finally:
            con.close()

    def test_answered_rows_do_not_hide_unanswered_rows_under_limit(self):
        for n in range(1, 5):
            self.issue('q-'+str(n))
        for q in questions(self.run)['questions']:
            self.answer(q)
        remaining = questions(self.run, limit=1)
        self.assertEqual([q['issue_id'] for q in remaining['questions']], ['q-4'])
        self.assertEqual(remaining['open_question_count'], 1)
        self.assertEqual(remaining['remaining_question_count'], 0)

    def test_partial_or_unrelated_answers_keep_question_and_wait(self):
        self.issue()
        q = questions(self.run)['questions'][0]
        for text in ('Yalnız bir kısmını biliyorum', 'Başka konudan bahsedelim'):
            self.assertFalse(self.answer(q, text=text, sufficient=False)['resumed'])
            self.assertEqual(waiting(self.run)['questions'][0]['scope_sha256'], q['scope_sha256'])
            self.assertEqual(len(active(self.run)), 1)

    def test_changed_source_scope_is_a_new_question(self):
        self.issue()
        q = questions(self.run)['questions'][0]
        self.answer(q)
        con = connect(self.run)
        try:
            con.execute("UPDATE open_issues SET question='Yeni revizyonun ödeme şartı nedir?'")
            con.commit()
        finally:
            con.close()
        new = waiting(self.run)['questions'][0]
        self.assertNotEqual(new['scope_sha256'], q['scope_sha256'])
        self.assertEqual(len(active(self.run)), 1)

    def test_restart_and_duplicate_answer_do_not_represent_or_resume_twice(self):
        self.issue()
        q = questions(self.run)['questions'][0]
        self.answer(q)
        self.assertIsNone(waiting(Path(str(self.run))))
        self.assertFalse(self.answer(q)['resumed'])
        self.assertIsNone(waiting(self.run))

    def test_answer_requiring_new_run_is_not_asked_again(self):
        self.issue()
        q = questions(self.run)['questions'][0]
        self.answer(q, new_run_required=True)
        self.assertIsNone(waiting(self.run))
        self.assertEqual(active(self.run)[0]['state'], 'new_run_required')

    def test_new_run_barrier_does_no_analysis_or_repeat_question(self):
        from workflow import advance
        self.issue()
        q = questions(self.run)['questions'][0]
        self.answer(q, new_run_required=True)
        with patch('run_compatibility.assert_compatible', side_effect=AssertionError('analysis resumed')):
            result = advance(self.run)
        self.assertEqual(result['status'], 'NEW_RUN_REQUIRED')
        self.assertNotIn('questions', result)
        self.assertFalse(result['deliverable_artifacts'])

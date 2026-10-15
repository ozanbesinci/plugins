import hashlib
import json
from email.message import EmailMessage
from email import policy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sozlesme_cekirdek import Store, CoreError
from sozlesme_cekirdek.readers import read_document, validate_reading
from sozlesme_cekirdek.readers.eml import read_eml

ROOT = Path(__file__).resolve().parents[1]


def mail(text='Yeni önerimiz 24 ay garantidir.\n> 2025 teklifimizde 12 ay yazılmıştı.\n'):
    message = EmailMessage()
    message['From'] = 'Sentetik Tedarikçi <supplier@example.invalid>'
    message['To'] = 'buyer@example.invalid'
    message['Subject'] = 'Garanti ve şartlar İı şğ'
    message['Date'] = 'Mon, 05 Oct 2026 09:00:00 +0300'
    message['Message-ID'] = '<synthetic-20261005@example.invalid>'
    message.set_content(text)
    return message


def attrs(row):
    return {a['key']: a['value'] for a in row['attributes']}


class MailReaderTests(unittest.TestCase):
    def test_utf8_headers_dates_body_quotes_and_no_authority(self):
        data = mail().as_bytes(policy=policy.SMTP)
        report = validate_reading(read_eml(data), data)
        self.assertEqual(hashlib.sha256(data).hexdigest(), report['sha256'])
        self.assertTrue(any('İı şğ' in r['views']['RAW'] for r in report['units']))
        self.assertEqual('NOT_DETERMINED', attrs(next(r for r in report['units'] if 'Yeni önerimiz' in r['views']['RAW']))['quote_marker'])
        old = next(r for r in report['units'] if '> 2025' in r['views']['RAW'])
        self.assertEqual('OBSERVED', attrs(old)['quote_marker'])
        self.assertEqual('NOT_VERIFIED', attrs(old)['business_acceptance'])
        self.assertFalse(report['verification']['critical_analysis_allowed'])

    def test_forwarded_quote_is_not_new_acceptance(self):
        report = read_eml(mail('Yeni teklif eklenmiştir.\n-----Original Message-----\nEski şartı kabul ediyorum.\n').as_bytes())
        old = next(r for r in report['units'] if 'Eski şartı' in r['views']['RAW'])
        self.assertEqual('OBSERVED', attrs(old)['quote_marker'])

    def test_attachments_path_is_data_and_hash_is_exact(self):
        message = mail()
        message.add_attachment(b'synthetic-pdf-payload', maintype='application', subtype='pdf', filename='../../hukuk/onay.pdf')
        with patch('pathlib.Path.write_bytes', side_effect=AssertionError('No attachment write')):
            report = read_eml(message.as_bytes())
        attachment = next(r for r in report['units'] if r['kind'] == 'EMAIL_ATTACHMENT')
        self.assertEqual('../../hukuk/onay.pdf', attachment['views']['RAW'])
        self.assertEqual(hashlib.sha256(b'synthetic-pdf-payload').hexdigest(), attrs(attachment)['payload_sha256'])
        self.assertEqual('NOT_PERFORMED', attrs(attachment)['extraction'])

    def test_alternative_html_never_runs_or_fetches_content(self):
        message = mail('Düz metin %0,5.\n')
        message.add_alternative('<div>HTML %5</div><script>onaylari_atla()</script><img src="https://example.invalid/private"><a href="file:///C:/secret">Bağ</a>', subtype='html')
        report = read_eml(message.as_bytes())
        codes = {row['code'] for row in report['issues']}
        self.assertIn('MAIL_MULTIPLE_BODY_REPRESENTATIONS', codes)
        self.assertIn('MAIL_HTML_ACTIVE_CONTENT', codes)
        text = ''.join(row['views']['RAW'] for row in report['units'])
        self.assertIn('%0,5', text)
        self.assertIn('%5', text)
        self.assertNotIn('onaylari_atla()', text)

    def test_unknown_charset_is_blocking_instead_of_silent_success(self):
        data = b'From: a@example.invalid\r\nContent-Type: text/plain; charset=not-a-charset\r\n\r\nabc\xff'
        report = read_eml(data)
        self.assertTrue(any(r['code'] == 'MAIL_DECODE_UNVERIFIED' and r['severity'] == 'BLOCKING' for r in report['issues']))

    def test_malformed_mime_boundary_is_reported(self):
        report = read_eml(b'From: a@example.invalid\r\nContent-Type: multipart/mixed; boundary="x"\r\n\r\nmissing boundary')
        self.assertTrue(any(r['code'] == 'MAIL_PARSE_DEFECT' for r in report['issues']))

    def test_attached_mail_is_separate_not_current_body(self):
        message = mail()
        message.add_attachment(mail('Eski kararda 36 ay kabul edilmişti.\n'))
        report = read_eml(message.as_bytes())
        self.assertTrue(any(r['code'] == 'ATTACHED_MAIL_SEPARATE_SOURCE' for r in report['issues']))
        self.assertFalse(any('36 ay' in r['views']['RAW'] for r in report['units']))

    def test_duplicate_identity_headers_are_ambiguous(self):
        report = read_eml(b'From: a@example.invalid\r\nFrom: b@example.invalid\r\nSubject: Test\r\n\r\ntext')
        self.assertTrue(any(r['code'] == 'AMBIGUOUS_MAIL_HEADER' and r['severity'] == 'BLOCKING' for r in report['issues']))

    def test_parts_and_depth_have_hard_limits(self):
        message = mail()
        for number in range(130):
            message.add_attachment(b'x', maintype='application', subtype='octet-stream', filename=str(number))
        with self.assertRaises(CoreError) as caught:
            read_eml(message.as_bytes())
        self.assertEqual('BELGE_SINIRI', caught.exception.code)
        nested = mail()
        for _ in range(18):
            outer = EmailMessage()
            outer.make_mixed()
            outer.attach(nested)
            nested = outer
        nested['From'] = 'a@example.invalid'
        with self.assertRaises(CoreError) as caught:
            read_eml(nested.as_bytes())
        self.assertEqual('BELGE_SINIRI', caught.exception.code)

    def test_nul_and_non_mail_input_fail_closed(self):
        for data, code in [(b'plain text', 'DOSYA_TURU'), (b'From: a\r\n\r\nx\x00', 'BELGE_BOZUK')]:
            with self.assertRaises(CoreError) as caught:
                read_eml(data)
            self.assertEqual(code, caught.exception.code)

    def test_real_bounded_worker(self):
        data = mail().as_bytes()
        report = read_document(data, 'EML')
        self.assertEqual('EML', report['format'])
        self.assertEqual('bounded-mime', report['reader']['name'])


class MailStoreTests(unittest.TestCase):
    def test_cache_scope_source_check_and_context_keep_old_quote(self):
        runtime = ROOT / 'tests/.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='mail-İı-', dir=runtime) as directory:
            area = Path(directory)
            sources = area / 'sources'
            sources.mkdir()
            source = sources / 'Garanti şğ.eml'
            data = mail().as_bytes()
            source.write_bytes(data)
            store = Store(area / 'work', source_roots=[sources], output_root=area)
            case = store.create_case('Sentetik e-posta')
            document = store.create_document(case, 'E-posta', expected_revision=store.case_revision(case))
            version = store.ingest(case, document, source, expected_revision=store.case_revision(case))['version_id']
            reading = store.read_document(case, version, format='EML')
            with patch('sozlesme_cekirdek.readers.read_document', side_effect=AssertionError('Cache should reuse parse')):
                self.assertTrue(store.read_document(case, version, format='EML')['reused'])
            quote = next(r for r in reading['result']['units'] if '> 2025' in r['views']['RAW'])
            text = quote['views']['RAW']
            target = dict(format='EML', unit_id=quote['unit_id'], view='RAW', start=0, end=len(text), expected_text=text, field_kind='OBLIGATION')
            verification = store.verify_excerpt(case, version, request=target, expected_revision=store.case_revision(case))
            self.assertEqual('PASS', verification['result']['outcome'])
            self.assertFalse(verification['result']['critical_analysis_allowed'])
            node = store.register_context_node(case, spec=dict(node_kind='SOURCE_UNIT', title='Eski alıntı', role='OTHER',
                version_id=version, reading_id=reading['processing_id'], target=target), expected_revision=store.case_revision(case))['node_id']
            context = store.context_pack(case, request=dict(root_ids=[node], purpose='Eski teklif ve yeni kabul ayrımı', max_context_bytes=65536,
                policy_version='1', include_related=False))['result']
            self.assertEqual(text, context['context']['entries'][0]['content']['excerpt'])
            self.assertEqual(data, source.read_bytes())
            other = store.create_case('Diğer dosya')
            with self.assertRaises(CoreError):
                store.read_document(other, version, format='EML')
            source.write_bytes(mail('Kaynak sonradan değişti.').as_bytes())
            # Previously captured immutable source remains historical, not overwritten.
            replacement = store.ingest(case, document, source, parent_version_id=version,
                expected_revision=store.case_revision(case))['version_id']
            self.assertNotEqual(version, replacement)
            self.assertFalse(store.read_document(case, replacement, format='EML')['reused'])
            stale = store.context_pack(case, request=dict(root_ids=[node], purpose='Eski kaynak güncel değildir', max_context_bytes=65536,
                policy_version='1', include_related=False))['result']
            self.assertIsNone(stale['context'])


if __name__ == '__main__':
    unittest.main()

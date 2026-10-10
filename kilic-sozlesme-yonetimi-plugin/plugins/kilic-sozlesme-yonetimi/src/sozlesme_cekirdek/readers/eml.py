"""Read-only bounded MIME inventory. Mail text is neither sender proof nor acceptance.

Attachments are hashed in memory, never extracted using their supplied filenames.
Alternative bodies and quoted text remain separate; no network or active HTML runs.
"""
import hashlib
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

from ..errors import CoreError
from .common import feature, issue, locator, result_base, unit

MAX_PARTS = 128
MAX_DEPTH = 16
MAX_PART_BYTES = 8 * 1024 * 1024


class InertHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.omitted = []
        self.blocked = []
        self.references = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template'}:
            self.omitted.append(tag)
            self.blocked.append(tag)
        if not self.blocked and tag in {'p', 'div', 'br', 'tr', 'li', 'blockquote'}:
            self.text.append('\n')
        self.references += sum(k in {'src', 'href', 'action'} for k, _ in attrs)

    def handle_endtag(self, tag):
        if self.blocked and tag == self.blocked[-1]:
            self.blocked.pop()
        if not self.blocked and tag in {'p', 'div', 'tr', 'li', 'blockquote'}:
            self.text.append('\n')

    def handle_data(self, data):
        if not self.blocked:
            self.text.append(data)


def _attrs(message, **extra):
    return dict(content_type=message.get_content_type(),
                disposition=message.get_content_disposition() or '',
                charset=message.get_content_charset() or '',
                sender_authentication='NOT_VERIFIED', business_acceptance='NOT_VERIFIED', **extra)


def _body_units(report, part, path, text, message, *, html=False):
    # Mark only explicit quote indicators. Absence of an indicator is NOT proof of a new offer.
    start = 0
    forwarded = False
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        marker = line.lstrip()
        if re.match(r'(-{2,}\s*(Original Message|Forwarded message|İleti aslı|İletilen ileti)|Begin forwarded message:)', marker, re.I):
            forwarded = True
        quoted = forwarded or marker.startswith('>')
        unit(report, 'EMAIL_BODY', locator(part=part, path=f'{path}/line/{number}'), line,
             attributes=_attrs(message, start=start, end=start + len(line),
                               quote_marker='OBSERVED' if quoted else 'NOT_DETERMINED',
                               representation='HTML_TEXT_UNVERIFIED' if html else 'DECODED_TEXT'))
        start += len(line)
    if not text:
        issue(report, 'MAIL_BODY_EMPTY', 'Boş metin parçası; okunabilir hüküm varsayılmadı.', locator(part=part, path=path))


def read_eml(data):
    if not isinstance(data, bytes) or len(data) > 64 * 1024 * 1024:
        raise CoreError('BELGE_SINIRI', 'EML kaynak sınırı 64 MiB')
    if b'\x00' in data:
        raise CoreError('BELGE_BOZUK', 'EML kaynağında NUL baytı')
    report = result_base(data, 'EML', 'bounded-mime', [])
    message = BytesParser(policy=policy.default).parsebytes(data)
    if not any(message.get(name) for name in ('From', 'To', 'Date', 'Subject', 'Message-ID')):
        raise CoreError('DOSYA_TURU', 'E-posta başlığı içeren EML gerekli')
    report['parts'].append({'name': 'message.eml', 'sha256': report['sha256'], 'size_bytes': len(data)})
    counts = {'parts': 0, 'attachments': 0, 'bodies': 0, 'quoted_lines': 0, 'nested_messages': 0}

    def inspect(msg, path, depth):
        if depth > MAX_DEPTH:
            raise CoreError('BELGE_SINIRI', 'MIME derinlik sınırı aşıldı')
        counts['parts'] += 1
        if counts['parts'] > MAX_PARTS:
            raise CoreError('BELGE_SINIRI', 'MIME parça sınırı aşıldı')
        part = 'mime/' + path
        if depth == 0:
            for number, (name, value) in enumerate(msg.items(), 1):
                unit(report, 'EMAIL_HEADER', locator(part=part, path=f'header/{number}/{name.lower()}'), str(value),
                     attributes=_attrs(msg, header_name=name, source_date=str(msg.get('Date', '')),
                                       header_interpretation='UNTRUSTED_REPORTED_METADATA'))
            for name in ('From', 'Date', 'Message-ID'):
                if len(msg.get_all(name, [])) > 1:
                    issue(report, 'AMBIGUOUS_MAIL_HEADER', f'Birden çok {name} başlığı.', severity='BLOCKING')
        if msg.get_content_type() in {'multipart/signed', 'multipart/encrypted', 'application/pkcs7-mime'}:
            issue(report, 'MAIL_SIGNATURE_NOT_VERIFIED', 'İmza/şifreleme ve gönderen kimliği doğrulanmadı.', locator(part=part), 'BLOCKING')
        if msg.get_content_type() == 'message/rfc822':
            # Preserve attached mail as a distinct source, not today's accepted terms.
            counts['nested_messages'] += 1
            blob = msg.as_bytes(policy=policy.default)
            if len(blob) > MAX_PART_BYTES:
                raise CoreError('BELGE_SINIRI', 'Ek e-posta boyut sınırı')
            report['parts'].append({'name': part, 'sha256': hashlib.sha256(blob).hexdigest(), 'size_bytes': len(blob)})
            issue(report, 'ATTACHED_MAIL_SEPARATE_SOURCE', 'Ek e-posta ayrı kaynak olarak alınmalı; güncel kabul sayılmadı.', locator(part=part), 'WARNING')
        elif msg.is_multipart():
            for number, child in enumerate(msg.iter_parts(), 1):
                inspect(child, f'{path}.{number}', depth + 1)
        else:
            blob = msg.get_payload(decode=True) or b''
            if len(blob) > MAX_PART_BYTES:
                raise CoreError('BELGE_SINIRI', 'MIME parça boyut sınırı aşıldı')
            report['parts'].append({'name': part, 'sha256': hashlib.sha256(blob).hexdigest(), 'size_bytes': len(blob)})
            filename = msg.get_filename()
            if filename is not None or msg.get_content_disposition() == 'attachment':
                counts['attachments'] += 1
                unit(report, 'EMAIL_ATTACHMENT', locator(part=part, path='attachment'), filename or '',
                     attributes=_attrs(msg, payload_sha256=hashlib.sha256(blob).hexdigest(), size_bytes=len(blob),
                                       extraction='NOT_PERFORMED', payload_interpretation='NOT_RUN'))
                issue(report, 'MAIL_ATTACHMENT_NOT_READ', 'Ek yalnız envanter/hash; içeriği ayrı sürüm olarak okunmalı.', locator(part=part))
            elif msg.get_content_type() in {'text/plain', 'text/html'}:
                counts['bodies'] += 1
                charset = msg.get_content_charset() or 'ascii'
                try:
                    text = blob.decode(charset, errors='strict')
                except (LookupError, UnicodeError):
                    text = blob.decode('utf-8', errors='replace')
                    issue(report, 'MAIL_DECODE_UNVERIFIED', 'Karakter kodlaması doğrulanamadı; kritik yorum engeli.', locator(part=part), 'BLOCKING')
                html = msg.get_content_type() == 'text/html'
                if html:
                    parser = InertHTML()
                    parser.feed(text)
                    parser.close()
                    text = ''.join(parser.text)
                    feature(report, 'html_external_references:' + path, parser.references, 'TESTED', 'NO_NETWORK_FETCH')
                    issue(report, 'MAIL_HTML_VISUAL_NOT_RUN', 'HTML metinleştirme kaynak görünümünü doğrulamaz; görsel inceleme gerekli.', locator(part=part))
                    if parser.omitted:
                        issue(report, 'MAIL_HTML_ACTIVE_CONTENT', 'Aktif/stil/şablon metni çalıştırılmadan atlandı.', locator(part=part), 'BLOCKING')
                _body_units(report, part, path, text, msg, html=html)
            else:
                issue(report, 'MAIL_INLINE_CONTENT_UNSUPPORTED', 'Metin dışı inline içerik ayrı kontrol gerektirir.', locator(part=part))
        for defect in msg.defects:
            issue(report, 'MAIL_PARSE_DEFECT', type(defect).__name__, locator(part=part), 'BLOCKING')

    inspect(message, '1', 0)
    for row in report['units']:
        row['attributes'].extend([{'key': 'root_message_date', 'value': str(message.get('Date', ''))},
                                  {'key': 'root_message_id', 'value': str(message.get('Message-ID', ''))}])
    if counts['bodies'] > 1:
        issue(report, 'MAIL_MULTIPLE_BODY_REPRESENTATIONS', 'Alternatif gövdeler ayrı korundu; biri otomatik doğru seçilmedi.')
    counts['quoted_lines'] = sum(any(a['key'] == 'quote_marker' and a['value'] == 'OBSERVED' for a in row['attributes']) for row in report['units'])
    for name, count in counts.items():
        feature(report, 'mail_' + name, count, 'TESTED', 'STRUCTURAL_INVENTORY_ONLY')
    issue(report, 'MAIL_NOT_AUTHORITY', 'Tarih/gönderen/alıcı ve kabul beyanı yalnız belge verisi; kimlik veya şirket onayı değildir.', severity='INFO')
    report['verification']['methods'] = ['BOUNDED_MIME_PARSE', 'DECODED_PART_HASH', 'EXPLICIT_QUOTE_MARKER_INVENTORY']
    report['fallback']['next'] = ['READ_RELEVANT_ATTACHMENTS_AS_SEPARATE_SOURCES', 'VERIFY_MESSAGE_HISTORY_AND_AUTHORITY']
    return report

"""Read the active session model/effort before analysis; no setup or network calls."""
from __future__ import annotations

import argparse
import json
import sys

from butce import read_session
from model_secimi import REQUIRED_MODEL, REQUIRED_EFFORT


WARNING = ('Modeli GPT-6.1, eforu High olarak değiştirin. '
           'Bu seçim doğrulanana kadar teklif analizine devam edemiyorum.')


def check_session(main_log, session_id):
    result = {'status': 'UNVERIFIED',
              'required': {'model': REQUIRED_MODEL, 'reasoning_effort': REQUIRED_EFFORT},
              'observed': None, 'message': WARNING}
    try:
        observed = read_session(main_log)
        if not session_id or observed['session_id'] != session_id:
            raise ValueError('Günlük aktif kullanıcı oturumuna ait değil.')
        result['observed'] = {key: observed[key] for key in ('model', 'reasoning_effort')}
        ready = result['observed'] == result['required']
        result['status'] = 'READY' if ready else 'WAITING_FOR_SELECTION'
        if ready:
            result['message'] = 'GPT-6.1 / High doğrulandı; teklif analizine devam edilebilir.'
    except (OSError, ValueError, KeyError, TypeError) as error:
        result['reason'] = str(error)
        result['message'] = 'Aktif oturumun model ve efor bilgisi doğrulanamadı. ' + WARNING
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main-log', required=True)
    parser.add_argument('--session-id', required=True)
    args = parser.parse_args(argv)
    result = check_session(args.main_log, args.session_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'READY' else 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

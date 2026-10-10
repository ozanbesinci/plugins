"""One bounded read in a fresh process, not an OS sandbox."""
import json
import sys
from ..errors import CoreError


def main():
    try:
        kind = sys.argv[1]
        data = sys.stdin.buffer.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024:
            raise CoreError("BELGE_SINIRI", "Kaynak sınırı aşıldı")
        if kind == "DOCX":
            from .docx import read_docx as reader
        elif kind == "XLSX":
            from .xlsx import read_xlsx as reader
        elif kind == "PDF":
            from .pdf import read_pdf as reader
        elif kind == "EML":
            from .eml import read_eml as reader
        else:
            raise CoreError("DOSYA_TURU", "Tanımlı okuyucu gerekli")
        result = reader(data)
        from . import validate_reading
        validate_reading(result, data)
        sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    except Exception as exc:
        result = {"error": exc.code if isinstance(exc, CoreError) else "OKUYUCU_HATASI",
                  "message": str(exc) if isinstance(exc, CoreError) else type(exc).__name__}
        sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        raise SystemExit(2)


if __name__ == "__main__":
    main()

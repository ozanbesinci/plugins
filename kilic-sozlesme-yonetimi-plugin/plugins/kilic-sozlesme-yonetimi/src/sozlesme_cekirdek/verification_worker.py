"""Fixed PDF page render worker. No implicit OCR, document repair or filesystem output."""
import json
import sys
from .errors import CoreError


def main():
    try:
        from .readers.pdf import render_pdf_page
        data = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise CoreError("BELGE_SINIRI", "PDF render kaynak sınırı")
        png = render_pdf_page(data, int(sys.argv[1]))
        if len(png) > 16 * 1024 * 1024:
            raise CoreError("BELGE_SINIRI", "PNG render çıktı sınırı")
        sys.stdout.buffer.write(png)
    except Exception as exc:
        result = {"error": exc.code if isinstance(exc, CoreError) else "RENDER_HATASI",
                  "message": str(exc) if isinstance(exc, CoreError) else type(exc).__name__}
        sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        raise SystemExit(2)


if __name__ == "__main__":
    main()

"""One hidden Excel instance; invoked only by the bounded copy-based runner."""
import argparse
import json
from pathlib import Path
from office_execution import windows_identity

def operate(args):
    excel=None;book=None
    result={'available':False,'attempt':args.attempt,'operation':args.operation}
    try:
        import win32com.client
        import win32process
        excel=win32com.client.DispatchEx('Excel.Application')
        excel.Visible=False;excel.DisplayAlerts=False;excel.AutomationSecurity=3;excel.EnableEvents=False
        _,pid=win32process.GetWindowThreadProcessId(excel.Hwnd)
        Path(args.receipt).write_text(json.dumps({'attempt':args.attempt,'pid':pid,'identity':windows_identity(pid)}),encoding='utf-8')
        source=Path(args.input)
        if args.operation=='pdf':
            from print_layout import build_print_workbook
            printed=source.with_name('print.xlsx');build_print_workbook(source,printed);source=printed
        book=excel.Workbooks.Open(str(source.resolve()),UpdateLinks=0,ReadOnly=args.operation=='pdf',AddToMru=False,IgnoreReadOnlyRecommended=True)
        if args.operation=='recalculate':excel.CalculateFullRebuild();book.Save()
        else:book.ExportAsFixedFormat(0,str(Path(args.output).resolve()))
        book.Close(False);book=None
        result.update(available=True,status='recalculated' if args.operation=='recalculate' else 'exported',excel_version=excel.Version)
    except Exception as exc:result['reason']='excel_worker_error:'+str(exc)
    finally:
        try:
            if book is not None:book.Close(False)
        except Exception:pass
        try:
            if excel is not None:excel.Quit()
        except Exception:pass
    # A hang during Close/Quit is also subject to the parent deadline.
    Path(args.result).write_text(json.dumps(result),encoding='utf-8')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--operation',choices=['recalculate','pdf'],required=True)
    for name in ('input','output','result','receipt','attempt'):ap.add_argument('--'+name,required=True)
    operate(ap.parse_args())

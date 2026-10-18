"""Inspect a Windows Installer database read-only; never run installation actions."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path

class Database:
    def __init__(self, path):
        self.api=C.WinDLL('msi',use_last_error=True)
        signatures={
            'MsiOpenDatabaseW':([W.LPCWSTR,C.c_void_p,C.POINTER(W.UINT)],W.UINT),
            'MsiDatabaseOpenViewW':([W.UINT,W.LPCWSTR,C.POINTER(W.UINT)],W.UINT),
            'MsiViewExecute':([W.UINT,W.UINT],W.UINT),
            'MsiViewFetch':([W.UINT,C.POINTER(W.UINT)],W.UINT),
            'MsiRecordGetStringW':([W.UINT,W.UINT,W.LPWSTR,C.POINTER(W.DWORD)],W.UINT),
            'MsiRecordReadStream':([W.UINT,W.UINT,C.c_void_p,C.POINTER(W.DWORD)],W.UINT),
            'MsiCloseHandle':([W.UINT],W.UINT),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.api,name);fn.argtypes=args;fn.restype=result
        self.handle=W.UINT()
        self.check(self.api.MsiOpenDatabaseW(str(Path(path).resolve()),None,C.byref(self.handle)))
    @staticmethod
    def check(result):
        if result:raise OSError('MSI read-only query failed: '+str(result))
    def records(self,sql):
        view=W.UINT();self.check(self.api.MsiDatabaseOpenViewW(self.handle,sql,C.byref(view)))
        try:
            self.check(self.api.MsiViewExecute(view,0))
            while True:
                row=W.UINT();rc=self.api.MsiViewFetch(view,C.byref(row))
                if rc==259:break
                self.check(rc)
                try:yield row
                finally:self.api.MsiCloseHandle(row)
        finally:self.api.MsiCloseHandle(view)
    def string(self,row,column):
        n=W.DWORD(32768);buf=C.create_unicode_buffer(n.value)
        self.check(self.api.MsiRecordGetStringW(row,column,buf,C.byref(n)))
        return buf.value
    def rows(self,table,columns):
        sql='SELECT '+','.join('`'+c+'`' for c in columns)+' FROM `'+table+'`'
        return [dict(zip(columns,[self.string(row,i+1) for i in range(len(columns))])) for row in self.records(sql)]
    def extract_stream(self,name,target):
        if "'" in name:raise ValueError('Unexpected stream name')
        rows=self.records("SELECT `Data` FROM `_Streams` WHERE `Name`='"+name+"'")
        count=0
        for row in rows:
            count+=1
            with Path(target).open('xb') as out:
                while True:
                    size=W.DWORD(1024*1024);buf=C.create_string_buffer(size.value)
                    self.check(self.api.MsiRecordReadStream(row,1,buf,C.byref(size)))
                    if not size.value:break
                    out.write(buf.raw[:size.value])
        if count!=1:raise ValueError('Missing/duplicate stream')
    def close(self):self.api.MsiCloseHandle(self.handle)


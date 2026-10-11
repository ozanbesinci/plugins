"""One strict interpretation of supported XLSX evidence address aliases."""
import re

def address(locator):
    values=[]
    for key in ('cell','range','cell_range'):
        value=locator.get(key)
        if value is None:continue
        if not isinstance(value,str) or not value.strip():
            raise ValueError('XLSX locator address must be a non-empty string')
        value=value.strip().upper()
        if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]*(?::[A-Z]{1,3}[1-9][0-9]*)?',value):
            raise ValueError('Invalid XLSX locator address')
        # A1 and A1:A1 are the same address, but a different cell/range is not.
        ends=value.split(':');canonical=ends[0] if len(ends)==2 and ends[0]==ends[1] else value
        values.append(canonical)
    if len(set(values))>1:raise ValueError('Conflicting XLSX locator address aliases')
    return values[0] if values else None

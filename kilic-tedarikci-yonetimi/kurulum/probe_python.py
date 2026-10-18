"""ASCII, stdlib-only interpreter identity; avoids Windows command-string quoting."""
import platform
import struct
import sys
import sysconfig
print(str(sys.version_info.major)+'.'+str(sys.version_info.minor)+':'+str(struct.calcsize('P')*8))
raise SystemExit(0 if platform.system()=='Windows' and sys.version_info[:2]==(3,14)
                 and struct.calcsize('P')==8 and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)

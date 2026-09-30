"""v4 entry point: native GPT-6.1/High subagents and evidence gates."""
from ajan_v4 import *
if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

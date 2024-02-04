"""Entry-point module, in case you use `python -m codeflow`.

Why does this file exist, and why `__main__`? For more info, read:

- https://www.python.org/dev/peps/pep-0338/
- https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""

import sys

from codeflow.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

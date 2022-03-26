import sys

print_prefix = "[djinni-build.py]"


def print_prefixed(message: str, file=sys.stdout):
    print(f'{print_prefix} {message}', file=file)

from pyrip.cli import rip
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f'usage: {sys.argv[0]} <apk>')
        sys.exit(1)


    rip()

from pyrip.cli import rip
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: pyrip <apk>')
        sys.exit(1)


    rip()

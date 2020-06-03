
import argparse
import multiprocessing
import sys

from PyQt5.QtWidgets import QApplication
from pychart.app import MainWindow, initApp, exportImage


def init():
    """
    Setup Python configuration
    """
    def excepthook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)

        if exc_type is KeyboardInterrupt:
            QApplication.quit()

    # use custom handler for exceptions when frozen
    if getattr(sys, 'frozen', False):
        sys.excepthook = excepthook

    # only the 'folk' method of starting a process is compatable with cx_Freeze
    multiprocessing.set_start_method('fork')


def gui(args):
    """
    Create and start windowed Qt application.
    """
    app = QApplication(sys.argv)
    initApp(app)

    path = args.input if hasattr(args, 'input') else None
    MainWindow.create(path)

    sys.exit(app.exec_())


def run(args):
    """
    Create Qt application and execute an image export.
    """
    app = QApplication(sys.argv)
    initApp(app)

    exportImage(args.input, args.output, args.width, args.height, app.quit)

    sys.exit(app.exec_())


def parse():
    """
    Parse command-line arguments
    """
    parser = argparse.ArgumentParser(description='python based chart design tool')
    parser.set_defaults(func=gui) # open gui by default

    subparsers = parser.add_subparsers(help='sub-command help')
    guiParser = subparsers.add_parser('gui', help='open gui application')
    guiParser.add_argument('input', type=str, metavar='file', help='pychart document filepath', nargs='?')
    guiParser.set_defaults(func=gui)

    runParser = subparsers.add_parser('run', help='generate chart image')
    runParser.add_argument('input', type=str, metavar='pychart-in', help='source pychart document filepath')
    runParser.add_argument('output', type=str, metavar='image-out', help='output image filepath')
    runParser.add_argument('--width', type=int, help='width in pixels (default: %(default)s)', default=640)
    runParser.add_argument('--height', type=int, help='height in pixels (default: %(default)s)', default=480)
    runParser.set_defaults(func=run)
    return parser.parse_args()


def main():
    init()
    args = parse()
    args.func(args)


if __name__ == "__main__":
    main()

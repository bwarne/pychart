
import contextlib
import os
import sys


@contextlib.contextmanager
def disconnectSignal(signal, slot):
    signal.disconnect(slot)
    yield
    signal.connect(slot)


def getResourcePath(relative_path):
    """Get absolute path to resource"""
    # if cx_freeze attribute found, use frozen resources
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)

    else: # use path to development resources
        base_path = os.path.abspath(os.path.dirname(sys.argv[0]))

    return os.path.join(base_path, 'resources', relative_path)


def readFile(path):
    with open(path) as f:
        return f.read()

def writeFile(path, data):
    with open(path, 'wb') as f:
        f.write(data)


def debugMethod(fn):
    def wrapped(*args, **kwargs):
        print(fn.__name__ + ' ⤵')
        fn(self, *args, **kwargs)
        print(fn.__name__ + ' ⤴')

    return wrapped


def debugClassMethod(fn):
    def wrapped(self, *args, **kwargs):
        print(self.__class__.__name__ + '::' + fn.__name__ + ' ⤵')
        fn(self, *args, **kwargs)
        print(self.__class__.__name__ + '::' + fn.__name__ + ' ⤴')

    return wrapped

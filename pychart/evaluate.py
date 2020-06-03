
import sys
import multiprocessing as mp
import multiprocessing.queues as mpq

from IPython.core.interactiveshell import InteractiveShell
from IPython.utils import io

from PyQt5.QtCore import QObject, QThread, pyqtSignal



class StdoutQueue(mpq.Queue):
    """
    Multiprocessing Queue to be used in place of a simple file descriptor.
    https://stackoverflow.com/a/39508408
    """
    def __init__(self, *args, **kwargs):
        ctx = mp.get_context()
        super().__init__(*args, **kwargs, ctx=ctx)

    def write(self, msg):
        self.put(msg)

    def flush(self):
        sys.__stdout__.flush()


class QueueMonitor(QThread):
    def __init__(self, queue, signal):
        super().__init__()
        self.queue = queue
        self.signal = signal
        self.start()

    def __del__(self):
        self.terminate()
        self.wait()

    def run(self):
        while True:
            self.signal.emit(self.queue.get())



def process(conn, stdout):
    shell = InteractiveShell()

    orig, sys.stdout = sys.stdout, stdout
    execRes = shell.run_cell(conn.recv())
    sys.stdout = orig

    res = (execRes.result, execRes.error_before_exec or execRes.error_in_exec)
    conn.send(res)



class Signals(QObject):
    started = pyqtSignal()
    finished = pyqtSignal()
    result = pyqtSignal(object)
    error = pyqtSignal()
    stdout = pyqtSignal(str)


class ProcessManager(QThread):
    def __init__(self):
        super().__init__()

        self.signals = Signals()

        self.busy = False
        self.proc = None
        self.pipe = mp.Pipe()

        self.stout = StdoutQueue()
        self.stoutMonitor = QueueMonitor(self.stout, self.signals.stdout)

    # def __del__(self):
    #     if self.isRunning():
    #         self.stop()

    def run(self):
        while True:
            # manager and process ends of a pipe
            (mgrConn, procConn) = self.pipe
            args = (procConn, self.stout)
            p = self.proc = mp.Process(target=process, args=args, daemon=True)
            p.start()
            p.join()
            p.close()

            self.busy = False
            # if process was not interrupted, we have a (result, exception)
            if mgrConn.poll():
                badType = False
                try:
                    res, exc = mgrConn.recv()
                    badType = type(res) != dict
                except AttributeError:
                    badType = True

                if not exc and badType:
                    err = "\nError: Return type must be a dict " \
                          "containing only primitives and collections."
                    self.signals.stdout.emit(err)
                    self.signals.error.emit()
                    continue

                if exc:
                    self.signals.error.emit()
                else:
                    self.signals.result.emit(res)

            self.signals.finished.emit()


            if self.isInterruptionRequested():
                break

    def stop(self):
        """Terminate the process and interrupt the thread."""
        self.requestInterruption()
        self.stopEvaluation()
        self.wait()

    def isEvaluating(self):
        return self.busy

    def startEvaluation(self, raw):
        """Evaluate raw code with process"""
        assert(not self.isEvaluating())
        self.busy = True
        (mgrConn, procConn) = self.pipe

        # clear any waiting code
        while procConn.poll():
            procConn.recv()

        mgrConn.send(raw)
        self.signals.started.emit()

    def stopEvaluation(self):
        # terminate the current process
        self.proc.terminate()

        # wait until process is no longer running
        while self.busy:
            pass

        # may need to resort to .kill()



if __name__ == '__main__':
    app = QCoreApplication(sys.argv)

    ph = ProcessHandler()
    ph.completed.connect(print)

    ph.start()
    ph.evaluate('1+1')
    ph.evaluate("print('hello world')")

    sys.exit(app.exec_())

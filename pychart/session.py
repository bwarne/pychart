
import sys
import multiprocessing as mp
import multiprocessing.queues as mpq

from IPython.core.interactiveshell import InteractiveShell

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .evaluate import ProcessManager





class Session(QObject):
    updateStarted = pyqtSignal()
    updateFinished = pyqtSignal()
    updateErrored = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = None

    def getDocument(self):
        return self.document

    def setDocument(self, document):
        self.document = document

    def update(self):
        """
        Evaluate the script to update the chart model with latest data sources.
        Changes to the chart model will trigger an update to the chart editor.
        """
        self.updateStarted.emit()
        shell = InteractiveShell()
        script = self.document.scriptEditorModel.getScript()
        execRes = shell.run_cell(script)

        # error with syntax or execution
        if execRes.error_before_exec or execRes.error_in_exec:
            self.updateErrored.emit()
            return

        # update document which triggers a chart update
        self.document.chartEditorModel.setChartDataSources(execRes.result)
        self.updateFinished.emit()



class AsyncSession(Session):

    updateStdout = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pm = ProcessManager()
        self.pm.start()
        self.pm.signals.started.connect(self.updateStarted)
        self.pm.signals.started.connect(self._updateStateChanged)
        self.pm.signals.finished.connect(self.updateFinished)
        self.pm.signals.finished.connect(self._updateStateChanged)
        self.pm.signals.error.connect(self.updateErrored)
        self.pm.signals.result.connect(self._updateSuccess)
        self.pm.signals.stdout.connect(self.updateStdout)


    def _updateStateChanged(self):
        """
        Signal may be out of sync with process.
        """
        # check process manager for evaluation state
        if self.pm.isEvaluating():
            self.updateStarted.emit()
        else:
            self.updateFinished.emit()

    def _updateSuccess(self, result):
        """
        Update completed successfully.
        """
        self.document.chartEditorModel.setChartDataSources(result)


    def update(self):
        # stop if already evaluating
        if self.pm.isEvaluating():
            self.pm.stopEvaluation()

        # start script evaluation
        script = self.document.scriptEditorModel.getScript()
        self.pm.startEvaluation(script)


    def stop(self):
        """
        Stop an update.
        """
        self.pm.stopEvaluation()










class AsyncSession(Session):

    updateStdout = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.pm = ProcessManager()
        self.pm.signals.started.connect(self.updateStarted)
        self.pm.signals.started.connect(self._updateStateChanged)
        self.pm.signals.finished.connect(self.updateFinished)
        self.pm.signals.finished.connect(self._updateStateChanged)
        self.pm.signals.error.connect(self.updateErrored)
        self.pm.signals.result.connect(self._updateSuccess)
        self.pm.signals.stdout.connect(self.updateStdout)


    def start(self):
        """
        Start the process manager within this session.
        """
        self.pm.start()


    def stop(self):
        """
        Stop the process manager within this session.
        """
        self.pm.stop()


    def _updateStateChanged(self):
        """
        Signal may be out of sync with process.
        """
        # check process manager for evaluation state
        if self.pm.isEvaluating():
            self.updateStarted.emit()
        else:
            self.updateFinished.emit()

    def _updateSuccess(self, result):
        """
        Update completed successfully.
        """
        self.document.chartEditorModel.setChartDataSources(result)


    def update(self):
        """
        Use the processes manager to perform an evaluation.
        """
        # stop if already evaluating
        if self.pm.isEvaluating():
            self.pm.stopEvaluation()

        # start script evaluation
        script = self.document.scriptEditorModel.getScript()
        self.pm.startEvaluation(script)


    def interrupt(self):
        """
        Interrupt an update.
        """
        self.pm.stopEvaluation()

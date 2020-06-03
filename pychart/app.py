
import functools
import os
import sys
import traceback
import json
import urllib
import multiprocessing

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QObject, pyqtSignal, QCoreApplication, Qt, QSettings
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QMainWindow, QAction, QDockWidget

from .common import readFile, writeFile, getResourcePath
from .chart import ChartEditor, ChartEditorModel
from .script import ScriptEditor, ScriptConsole, ScriptEditorModel
from .session import Session, AsyncSession

APP_NAME = 'pychart'
UNTITLED_TITLE = 'untitled'
CHART_EXT = '.cht'
IMAGE_EXT = '.png'
UNTITLED_CHART_NAME = UNTITLED_TITLE + CHART_EXT
UNTITLED_IMAGE_NAME = UNTITLED_TITLE + IMAGE_EXT
DEFAULT_CHART_NAME = 'default' + CHART_EXT



def initApp(app):
    """
    Initialize QApplication configuration
    """
    # apply defaults for QSettings
    QCoreApplication.setOrganizationName(APP_NAME)
    QCoreApplication.setApplicationName(APP_NAME)

    # apply stylesheet to app
    path = getResourcePath('style.qss')
    app.setStyleSheet(readFile(path))



def getExampleIndex():
    """
    Generate a mapping of example names to example filepaths.
    """
    # load example index
    path = getResourcePath('examples/index.json')
    index = json.loads(readFile(path))

    # map to full file path
    for k,v in index.items():
        index[k] = getResourcePath(os.path.join('examples', v))

    return index




def exportImage(documentPath, imagePath, width, height, callback):
    """
    Create a chart from the given document and export as an image to the
    specified image path.
    """
    document = Document.fromFile(documentPath)

    chartEditor = ChartEditor()
    chartEditor.setModel(document.chartEditorModel)

    def imageRequestCallback(imageData):
        writeFile(imagePath, imageData)
        callback()

    def chartUpdatedCallback():
        chartEditor.requestImage(imageRequestCallback, width, height)

    chartEditor.handler.chartUpdated.connect(chartUpdatedCallback)

    session = Session()
    session.setDocument(document)
    session.update()


class DocumentParseError(Exception):
    pass


class Document(QObject):
    VERSION = 1

    wasModified = pyqtSignal()

    def __init__(self, chart=None, script=None):
        super().__init__()

        self.filepath = None
        self.isModified = False
        self.chartEditorModel = chart or ChartEditorModel()
        self.scriptEditorModel = script or ScriptEditorModel()

        self.wasModified.connect(self.handleModification)
        self.chartEditorModel.wasModified.connect(self.wasModified)
        self.scriptEditorModel.wasModified.connect(self.wasModified)

    def handleModification(self):
        self.isModified = True

    def getChartEditorModel(self):
        return self.chartEditorModel

    def getScriptEditorModel(self):
        return self.scriptEditorModel

    def serialize(self):
        return {
            '_version_': self.VERSION,
            'chart': self.chartEditorModel.serialize(),
            'script': self.scriptEditorModel.serialize(),
        }

    @classmethod
    def unserialize(cls, data):
        chart = ChartEditorModel.unserialize(data['chart'])
        script = ScriptEditorModel.unserialize(data['script'])
        return cls(chart, script)

    def toFile(self, filepath):
        data = self.serialize()
        self.filepath = filepath
        self.isModified = False

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=1)

    @classmethod
    def fromFile(cls, filepath, template=False):

        try:
            data = json.loads(readFile(filepath))
            instance = cls.unserialize(data)
        except KeyError as e:
            msg = f"Document missing key: {e.args[0]}"
            raise DocumentParseError(msg)

        if not template:
            instance.filepath = filepath

        return instance



class MainWindow(QMainWindow):
    EDITOR_VISIBILITY_TEXT = ["Show Editor", "Hide Editor"]
    CONSOLE_VISIBILITY_TEXT = ["Show Console", "Hide Console"]
    WINDOW_OFFSET = 20

    instances = []

    def __init__(self, parent=None):
        super().__init__(parent)

        # printrefs('__init__', self)
        # store reference to this instance
        self.instances.append(self)

        # remove reference on window close
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.destroyed.connect(lambda: MainWindow.instances.remove(self))

        # persistant application settings
        self.settings = QSettings()

        # create and start evaluator session
        self.session = AsyncSession(self)
        self.session.start()
        self.chartEditor = ChartEditor()
        self.scriptEditor = ScriptEditor()
        self.scriptConsole = ScriptConsole()

        # listen for update errors
        self.session.updateErrored.connect(self.onEvaluationError)

        # session listens to script editor buttons
        self.scriptEditor.startEvaluation.connect(self.startEvaluation)
        self.scriptEditor.stopEvaluation.connect(self.stopEvaluation)

        # script editor listens to session state
        self.session.updateStarted.connect(self.scriptEditor.evaluationStarted)
        self.session.updateFinished.connect(self.scriptEditor.evaluationStopped)

        # script console listens to session stdout
        self.session.updateStdout.connect(self.scriptConsole.insertAnsiText)


        self.document = None
        self.showConsoleOnError = True
        self.unsavedChanges = False


        # self.setWindowTitle()
        self.resize(1400,500)
        self.setupMenuBar()

        self.scriptEditorDockWidget = QDockWidget("Editor", self)
        self.scriptEditorDockWidget.setObjectName("Editor")
        self.scriptEditorDockWidget.setWidget(self.scriptEditor)
        self.scriptEditorDockWidget.visibilityChanged.connect(
            self.setEditorVisibility
        )

        self.scriptConsoleDockWidget = QDockWidget("Console", self)
        self.scriptConsoleDockWidget.setObjectName("Console")
        self.scriptConsoleDockWidget.setWidget(self.scriptConsole)
        self.scriptConsoleDockWidget.visibilityChanged.connect(
            self.setConsoleVisibility
        )

        self.setCentralWidget(self.chartEditor)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.scriptEditorDockWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.scriptConsoleDockWidget)


        self.restoreWindowSettings()


    # def __del__(self):
    #     print(self.__class__.__name__ + '::__del__')


    def closeEvent(self, event):
        """
        Window received a close request.
        """
        if not self.saveMaybe():
            event.ignore()
            return

        # can't rely on destructor so cleanup here
        self.session.stop()

        self.storeWindowSettings()

        super().closeEvent(event)


    def storeWindowSettings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())


    def restoreWindowSettings(self):
        if val := self.settings.value("geometry"):
            self.restoreGeometry(val)

        if val := self.settings.value("windowState"):
            self.restoreState(val)


    def setupMenuBar(self):

        mb = self.menuBar()

        ## file menu ##
        menu = mb.addMenu("File")

        actn = QAction("New", self)
        actn.setShortcut('Ctrl+N')
        actn.triggered.connect(self.new)
        menu.addAction(actn)

        actn = QAction("Open...", self)
        actn.setShortcut('Ctrl+O')
        actn.triggered.connect(self.open)
        menu.addAction(actn)

        menu.addSeparator()

        actn = QAction("Close", self)
        actn.setShortcut('Ctrl+W')
        actn.triggered.connect(self.close)
        menu.addAction(actn)

        actn = QAction("Save", self)
        actn.setShortcut('Ctrl+S')
        actn.triggered.connect(self.save)
        menu.addAction(actn)

        actn = QAction("Save As...", self)
        actn.setShortcut('Shift+Ctrl+S')
        actn.triggered.connect(self.saveAs)
        menu.addAction(actn)


        ## view menu ##
        menu = mb.addMenu("View")

        self.toggleEditorVisibilityAction = actn = QAction('', self)
        self.setEditorVisibility(True)
        actn.setShortcut('Ctrl+1')
        actn.triggered.connect(self.toggleEditorVisibility)
        menu.addAction(actn)

        self.toggleConsoleVisibilityAction = actn = QAction('', self)
        self.setConsoleVisibility(False)
        actn.setShortcut('Ctrl+2')
        actn.triggered.connect(self.toggleConsoleVisibility)
        menu.addAction(actn)

        menu.addSeparator()

        actn = QAction("Show Console on Errors", self)
        actn.setCheckable(True)
        actn.setChecked(True)
        actn.triggered.connect(self.setShowConsoleOnError)
        menu.addAction(actn)


        ## script menu ###
        menu = mb.addMenu("Script")

        actn = QAction("Execute", self)
        actn.setShortcut('Shift+Return')
        actn.triggered.connect(self.startEvaluation)
        menu.addAction(actn)

        actn = QAction("Stop", self)
        actn.setShortcut('Shift+Delete')
        actn.triggered.connect(self.stopEvaluation)
        menu.addAction(actn)

        ## chart menu ###
        menu = mb.addMenu("Chart")

        actn = QAction("Export to Image...", self)
        actn.setShortcut('Ctrl+E')
        actn.triggered.connect(self.requestExportToFile)
        menu.addAction(actn)

        actn = QAction("Export to Clipboard...", self)
        actn.setShortcut('Shift+Ctrl+E')
        actn.triggered.connect(self.requestExportToClipboard)
        menu.addAction(actn)

        ## examples menu
        menu = mb.addMenu("Examples")

        for name, path in getExampleIndex().items():
            actn = QAction(name, self)
            fxn = functools.partial(self.new, path, True)
            actn.triggered.connect(fxn)
            menu.addAction(actn)


    def setEditorVisibility(self, state):
        text = self.EDITOR_VISIBILITY_TEXT[state]
        self.toggleEditorVisibilityAction.setText(text)


    def toggleEditorVisibility(self):
        state = self.scriptEditorDockWidget.isVisible()
        self.scriptEditorDockWidget.setVisible(not state)


    def setConsoleVisibility(self, state):
        text = self.CONSOLE_VISIBILITY_TEXT[state]
        self.toggleConsoleVisibilityAction.setText(text)


    def toggleConsoleVisibility(self):
        state = self.scriptConsoleDockWidget.isVisible()
        self.scriptConsoleDockWidget.setVisible(not state)


    def setShowConsoleOnError(self, checked):
        self.showConsoleOnError = checked


    def startEvaluation(self):
        # reset the console for new evaluation
        self.scriptConsole.clear()
        self.session.update()


    def stopEvaluation(self):
        self.session.interrupt()


    def onEvaluationError(self):
        if self.showConsoleOnError:
            self.scriptConsoleDockWidget.setVisible(True)


    def getDocument(self):
        return self.document

    def setDocument(self, document):
        self.document = document

        self.session.setDocument(document)
        self.chartEditor.setModel(self.document.chartEditorModel)
        self.scriptEditor.setModel(self.document.scriptEditorModel)
        self.document.wasModified.connect(self.documentWasModified)
        self.scriptConsole.clear()


    def documentWasModified(self):
        self.setWindowModified(True)


    @staticmethod
    def create(path=None, template=False):
        if not path:
            path = getResourcePath(DEFAULT_CHART_NAME)
            template = True

        doc = Document.fromFile(path, template)

        # new offset based on number of current instances
        offset = len(MainWindow.instances) * MainWindow.WINDOW_OFFSET
        w = MainWindow()

        w.setWindowTitle(UNTITLED_TITLE if template else os.path.basename(path))
        w.setDocument(doc)
        w.session.update()

        w.show()
        w.move(w.x() + offset, w.y())

        return w


    def new(self, path=None, template=False):
        """
        Create a new window from this instance.
        """
        # save current window settings so they are reflected in new window
        self.storeWindowSettings()

        try:
            self.create(path, template)

        except DocumentParseError:
            name = os.path.basename(path)
            msg = f"Unable to open '{name}'"
            QMessageBox.critical(self, "Application", msg)
            return False


    def open(self, path=None, template=False):
        """
        Open file in new window.
        """
        # if path not specified, use open file dialog
        if not path:
            path = os.path.expanduser('~')
            (path, _) = QFileDialog.getOpenFileName(self, 'Open File', path)
            if not path:
                return False

        self.new(path, template)
        return True


    def save(self):
        """
        Returns True if file was saved, otherwise False
        """
        doc = self.session.getDocument()
        if doc.filepath:
            doc.toFile(doc.filepath)
            self.setWindowModified(False)
            return True
        else:
            return self.saveAs()

    def saveAs(self):
        """
        Returns True if file was saved, otherwise False
        """
        defaultPath = os.path.join(os.path.expanduser('~'), UNTITLED_CHART_NAME)

        # check for last used save directory
        if saveDirectory := self.settings.value("saveDirectory"):
            defaultPath = os.path.join(saveDirectory, UNTITLED_CHART_NAME)

        (path, _) = QFileDialog.getSaveFileName(self, 'Save File', defaultPath)
        if not path:
            return False

        # store latest save directory path
        self.settings.setValue("saveDirectory", os.path.dirname(path))

        self.session.getDocument().toFile(path)
        self.setWindowTitle(os.path.basename(path))
        self.setWindowModified(False)

        return True


    def saveMaybe(self):
        """
        Returns False if file is modified and user cancels the operation,
        otherwise it returns True.
        """
        doc = self.session.getDocument()
        if not doc or not doc.isModified:
            return True

        msg = "The file has been modified. Do you want to save your changes?"
        btns = QMessageBox.Save | QMessageBox.Cancel | QMessageBox.Discard
        res = QMessageBox.warning(self, "Application", msg, btns)

        if res == QMessageBox.Save:
            return self.save()
        elif res == QMessageBox.Cancel:
            return False
        elif res == QMessageBox.Discard:
            return True


    def requestExportToFile(self):
        self.chartEditor.requestImage(self.exportImageToFile)


    def requestExportToClipboard(self):
        self.chartEditor.requestImage(self.exportImageToClipboard)


    def exportImageToFile(self, imageData):
        path = self.session.document.filepath
        if path:
            (root, ext) = os.path.splitext(path)
            path = root + '.png'
        else:
            path = os.path.join(os.path.expanduser('~'), UNTITLED_IMAGE_NAME)

        (path, _) = QFileDialog.getSaveFileName(self, 'Save File', path)
        if not path:
            return

        writeFile(path, imageData)


    def exportImageToClipboard(self, imageData):
        img = QImage.fromData(imageData)
        pixmap = QPixmap.fromImage(img)
        QApplication.clipboard().setPixmap(pixmap)

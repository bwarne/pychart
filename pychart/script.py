
import asyncio
import re
import traceback

import multiprocessing as mp
import time

from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, \
                            QTextEdit, QStyle, QLabel
from PyQt5.QtCore import Qt, QObject, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetrics, QColor
from PyQt5.Qsci import QsciScintilla, QsciLexerPython

from .common import disconnectSignal


class ScriptConsole(QTextEdit):
    #https://stackoverflow.com/a/44076754
    ANSI_MATCHER = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Console")

        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(12)

        # self.textEdit = QTextEdit()
        self.setProperty('class', 'Console')
        self.setFont(font)
        # self.textEdit.setTextColor(Qt.red)
        self.setReadOnly(True)


    def insertAnsiText(self, ansi):
        text = self.ANSI_MATCHER.sub('', ansi)
        self.insertPlainText(text)



class PythonTextField(QsciScintilla):
    ARROW_MARKER_NUM = 8
    DEFAULT_SIZE = 400

    shiftReturnPressed = pyqtSignal()
    shiftBackspacePressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set the default font
        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(12)
        self.setFont(font)
        self.setMarginsFont(font)



        # Margin 0 is used for line numbers
        fontmetrics = QFontMetrics(font)
        self.setMarginsFont(font)
        self.setMarginWidth(0, fontmetrics.width("0000"))
        self.setMarginLineNumbers(0, True)
        self.setMarginsBackgroundColor(QColor("#cccccc"))

        self.setTabWidth(4)


        # # Clickable margin 1 for showing markers
        # self.setMarginSensitivity(1, True)
        # self.marginClicked.connect(self.on_margin_clicked)
        # self.markerDefine(QsciScintilla.RightArrow,
        #     self.ARROW_MARKER_NUM)
        # self.setMarkerBackgroundColor(QColor("#ee1111"),
        #     self.ARROW_MARKER_NUM)

        # Brace matching: enable for a brace immediately before or after
        # the current position
        #
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        # Current line visible with special background color
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#ffe4e4"))

        # Set Python lexer
        # Set style for Python comments (style number 1) to a fixed-width
        # courier.
        #

        lexer = QsciLexerPython()
        lexer.setDefaultFont(font)
        self.setLexer(lexer)
        text = bytearray(str.encode("Courier"))
        self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, 1, text)
        self.SendScintilla(QsciScintilla.SCI_STYLESETSIZE, 1, 12)


        # Don't want to see the horizontal scrollbar at all
        # Use raw message to Scintilla here (all messages are documented
        # here: http://www.scintilla.org/ScintillaDoc.html)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)
        self.setScrollWidth(1)

        # not too small
        # self.setMinimumSize(500, 450)
    #
    # def on_margin_clicked(self, nmargin, nline, modifiers):
    #     # Toggle marker for the line the margin was clicked on
    #     if self.markersAtLine(nline) != 0:
    #         self.markerDelete(nline, self.ARROW_MARKER_NUM)
    #     else:
    #         self.markerAdd(nline, self.ARROW_MARKER_NUM)

    def keyPressEvent(self, e):
        # intercept special key combos
        if (e.key() == Qt.Key_Return and e.modifiers() == Qt.ShiftModifier):
            self.shiftReturnPressed.emit()

        elif (e.key() == Qt.Key_Backspace and e.modifiers() == Qt.ShiftModifier):
            self.shiftBackspacePressed.emit()

        elif (e.key() == Qt.Key_Tab):
            line,idx = self.getCursorPosition()
            self.insertAt(4 * ' ', line, idx)
            self.setCursorPosition(line, idx + 4)

        else:
            super().keyPressEvent(e)

    def sizeHint(self):
        return QSize(self.DEFAULT_SIZE, self.DEFAULT_SIZE)


class ScriptEditorControlBar(QWidget):

    def __init__(self, parent = None):
        super().__init__(parent)

        self.startButton = btn = QPushButton('')
        btn.setProperty('class', 'ControlBarButton')
        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        btn.setIcon(icon)
        btn.setIconSize(QSize(12,12))

        # btn.setFlat(True)
        # btn.setMaximumWidth(40)
        # btn.setContentsMargins(0, 0, 0, 0)

        self.stopButton = btn = QPushButton('')
        btn.setProperty('class', 'ControlBarButton')
        icon = self.style().standardIcon(QStyle.SP_MediaStop)
        btn.setIcon(icon)
        btn.setIconSize(QSize(12,12))
        # btn.setEnabled(False)
        # btn.setFlat(True)
        # btn.setMaximumWidth(40)
        # btn.setContentsMargins(0, 0, 0, 0)

        self.statusLabel = lbl = QLabel('')

        layout = QHBoxLayout()
        layout.setContentsMargins(10,0,10,0)
        # layout.setSpacing(0)    # space between buttons
        layout.addWidget(self.startButton)
        layout.addWidget(self.stopButton)
        layout.addStretch()     # fill space right of buttons
        layout.addWidget(self.statusLabel)

        self.setLayout(layout)
        # self.setFixedHeight(25)

        #
        # self.startButton.clicked.connect(lambda: print('foo'))


    def setStatus(self, text):
        self.statusLabel.setText(text)


class ScriptEditorModel(QObject):
    VERSION = 1
    DEFAULT_SCRIPT = '{}'

    dataChanged = pyqtSignal()
    wasModified = pyqtSignal()

    def __init__(self, script=None):
        super().__init__()
        self.script = script if script else self.DEFAULT_SCRIPT

    def getScript(self):
        return self.script

    def setScript(self, script):
        self.script = script
        self.wasModified.emit()
        self.dataChanged.emit()

    def serialize(self):
        return {
            '_version_': self.VERSION,
            'script': self.script,
        }

    @classmethod
    def unserialize(cls, data):
        return cls(data['script'])



class ScriptEditor(QWidget):
    # dataChanged = pyqtSignal()
    startEvaluation = pyqtSignal()
    stopEvaluation = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.model = None

        self.controlBar = ScriptEditorControlBar()
        self.controlBar.startButton.pressed.connect(self.startEvaluation)
        self.controlBar.stopButton.pressed.connect(self.stopEvaluation)

        self.pythonTextField = PythonTextField()
        self.pythonTextField.shiftReturnPressed.connect(self.startEvaluation)
        self.pythonTextField.shiftBackspacePressed.connect(self.stopEvaluation)
        self.pythonTextField.textChanged.connect(self.scriptTextChanged)

        layout = QVBoxLayout()
        layout.setProperty('class', 'CodeEditorLayout')
        layout.setSpacing(2)
        layout.setContentsMargins(0,4,0,0)
        layout.addWidget(self.controlBar)
        layout.addWidget(self.pythonTextField)
        self.setLayout(layout)

    def getModel(self):
        return self.model

    def setModel(self, model):
        self.model = model
        self.model.dataChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """Refresh the widget with model data"""
        # update editor text without signaling self
        with disconnectSignal(self.pythonTextField.textChanged, self.scriptTextChanged):
            self.pythonTextField.setText(self.model.getScript())

    def scriptTextChanged(self):
        # text changed in widget, so update model but ignore change signal
        with disconnectSignal(self.model.dataChanged, self.refresh):
            self.model.setScript(self.pythonTextField.text())

    def evaluationStarted(self):
        self.controlBar.setStatus('Busy')
        # self.controlBar.stopButton.setEnabled(True)

    def evaluationStopped(self):
        self.controlBar.setStatus('Idle')
        # self.controlBar.stopButton.setEnabled(False)

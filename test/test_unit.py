import sys
import time
import unittest

from pychart.app import Document
from pychart.session import Session, AsyncSession


class TestSession(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.document = Document()
        self.session.setDocument(self.document)

    def tearDown(self):
        pass

    def test_sessionUpdateConstant(self):
        script = "{'foo': 1}"
        self.document.getScriptEditorModel().setScript(script)
        self.session.update()
        res = self.document.getChartEditorModel().getChartDataSources()
        self.assertEqual(res, {'foo': 1})


    def test_sessionUpdateFunction(self):
        script = """
        def bar():
            return [1,2,3]

        {'foo': bar()}
        """
        self.document.getScriptEditorModel().setScript(script)
        self.session.update()
        res = self.document.getChartEditorModel().getChartDataSources()
        self.assertEqual(res, {'foo': [1,2,3]})



def test_asyncSessionUpdateConstant(qtbot):
    script = "{'foo': 1}"

    session = AsyncSession()
    document = Document()
    document.getScriptEditorModel().setScript(script)
    session.setDocument(document)
    session.start()

    with qtbot.waitSignal(session.updateFinished, timeout=10000) as blocker:
        session.update()

    session.stop()

    res = document.getChartEditorModel().getChartDataSources()
    assert(res == {'foo': 1})


def test_asyncSessionUpdateFunction(qtbot):
    script = """
    def bar():
        return [1,2,3]

    {'foo': bar()}
    """

    session = AsyncSession()
    document = Document()
    document.getScriptEditorModel().setScript(script)
    session.setDocument(document)
    session.start()

    with qtbot.waitSignal(session.updateFinished, timeout=10000) as blocker:
        session.update()

    session.stop()

    res = document.getChartEditorModel().getChartDataSources()
    assert(res == {'foo': [1,2,3]})


def test_asyncSessionUpdateInterrupt(qtbot):
    script = """"
    import time
    time.sleep(10)

    {'foo': 1}
    """

    session = AsyncSession()
    document = Document()
    document.getScriptEditorModel().setScript(script)
    session.setDocument(document)
    session.start()

    # interrupting shouldn't take longer than 5 seconds
    with qtbot.waitSignal(session.updateFinished, timeout=5000) as blocker:
        session.update()
        time.sleep(1)
        session.interrupt()

    session.stop()

    res = document.getChartEditorModel().getChartDataSources()
    assert(res == {})

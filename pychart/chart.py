
import copy
import simplejson as json
import sys
import os
import random
import pprint
import urllib
from queue import Queue

from PyQt5 import QtCore, QtWidgets, QtGui, QtWebEngineWidgets
from PyQt5.QtCore import Qt, QObject, QJsonValue, pyqtSignal, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

from .common import disconnectSignal, debugClassMethod, getResourcePath

## debug chart
# import os
# os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '12345'

from pprint import pprint

def cleanLayout(layout):
    """
    Remove unneccesary data from layout.
    """
    try:
        if layout['xaxis']['autorange']:
            del layout['xaxis']['range']
    except KeyError:
        pass

    try:
        if layout['yaxis']['autorange']:
            del layout['yaxis']['range']
    except KeyError:
        pass



def removeSourcesFromTraces(traces):
    """
    Remove source data from chart traces data.

    not yet defined:
    {'mode': 'markers', 'type': 'scatter'}

    simple:
    {
      'meta': {'columnNames': {'x': 'inc'}},
      'x': [],
      'xsrc': 'inc'
    }

    extra data (header, marker, etc)
    {
      'header': {'fill': {'color': [], 'colorsrc': 'inc'}},
      'meta': {'columnNames': {'header': {'fill': {'color': 'inc'}}}},
    }


    {
        'cells': {'values': [[],[]],
                 'valuessrc': ['sin', 'rand']},
        'header': {'values': [],
                 'valuessrc': 'inc'},
        'meta': {'columnNames': {'cells': {'values': 'sin - rand'},
                               'header': {'values': 'inc'}}
    }

    {
        'cells': {},
        'header': {},
        'meta': {'columnNames': {'cells': {'values': ''},
                                'header': {'values': ''}}
    },
    """
    def delete(a, b):
        for k,v in a.items():
            if type(v) is dict:
                delete(v, b[k])

            elif type(v) is str:
                # skip unset source name
                if not v:
                    continue

                del b[k]
            else:
                assert(False)

    # strip values from data
    for trace in traces:
        # if trace sources are not yet defined
        if 'meta' not in trace:
            continue

        delete(trace['meta']['columnNames'], trace)



def insertSourcesIntoTraces(traces, dataSources):
    """
    Insert sources in to trace data.
    """
    def insert(a, b):
        for k,v in a.items():
            if type(v) is dict:
                insert(v, b[k])

            # if v is a source title
            elif type(v) is str:
                # skip if not set
                if not v:
                    continue

                # get data source
                src = b[k + 'src']

                # if single data source
                if type(src) is str:
                    if src in dataSources:
                        b[k] = dataSources[src]

                    else: # source not found
                        a[k] = ''

                # else if multiple data sources
                elif type(src) is list:
                    # if any data sources match
                    if set(src).intersection(dataSources.keys()):
                        b[k] = [dataSources[s] for s in src if s in dataSources]
                    else:
                        a[k] = ''

                else:
                    assert(False)

            else:
                assert(False)

    # strip values from data
    for trace in traces:
        # if trace sources are not yet defined
        if 'meta' not in trace:
            continue

        insert(trace['meta']['columnNames'], trace)



class WebCallHandler(QObject):
    # python -> javascript
    updateChartStateSignal = pyqtSignal(str)
    requestImageSignal = pyqtSignal(int, int)

    # javscript -> python signals
    chartReady = pyqtSignal()
    chartUpdated = pyqtSignal()
    dataChanged = pyqtSignal(list)
    layoutChanged = pyqtSignal(dict)
    imageReady = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.editorHasMounted = False


    # python -> javascript
    def updateChartState(self, data):
        """Wrap signal to convert python data to json"""
        assert(self.editorHasMounted)
        jsn = json.dumps(data, iterable_as_array=True)
        self.updateChartStateSignal.emit(jsn);

    def requestImage(self, width, height):
        width = width if width else 0
        height = height if height else 0
        self.requestImageSignal.emit(width, height)


    # javascript -> python
    @pyqtSlot()
    def chartDidMount(self):
        self.editorHasMounted = True
        self.chartReady.emit()

    @pyqtSlot()
    def emitChartUpdated(self):
        self.chartUpdated.emit()

    @pyqtSlot(str)
    def dataChangedJson(self, jsn):
        self.dataChanged.emit(json.loads(jsn));

    @pyqtSlot(str)
    def layoutChangedJson(self, jsn):
        self.layoutChanged.emit(json.loads(jsn));


    @pyqtSlot(str)
    def emitImageReady(self, dataUrl):
        self.imageReady.emit(dataUrl)



class ChartEditorModel(QObject):
    VERSION = 1

    dataChanged = pyqtSignal()
    wasModified = pyqtSignal()

    def __init__(self, data=None):
        super().__init__()

        self.data = data or {
            'dataSources': {},
            'data': [],
            'layout': {},
        }

    def serialize(self):
        return {
            '_version_': self.VERSION,
            'data': self.data['data'],
            'layout': self.data['layout'],
        }

    @classmethod
    def unserialize(cls, data):
        res = {
            'dataSources': {},
            'data': data['data'],
            'layout': data['layout'],
        }
        return cls(res)


    def getChartDataSources(self):
        return self.data['dataSources']

    # @debugClassMethod
    def setChartDataSources(self, dataSources):
        if self.data['dataSources'] != dataSources:
            self.data['dataSources'] = dataSources
            self.dataChanged.emit()

    def getChartData(self):
        return self.data['data']

    # @debugClassMethod
    def setChartData(self, data):
        if self.data['data'] != data:
            self.data['data'] = data
            self.dataChanged.emit()
            self.wasModified.emit()

    def getChartLayout(self):
        return self.data['layout']

    # @debugClassMethod
    def setChartLayout(self, layout):
        if self.data['layout'] != layout:
            self.data['layout'] = layout
            self.dataChanged.emit()
            self.wasModified.emit()



class ChartEditor(QtWebEngineWidgets.QWebEngineView):
    def __init__(self):
        QtWebEngineWidgets.QWebEngineView.__init__(self)

        # init queue
        self.imageRequestCallbackQueue = Queue()

        # disable context menu
        self.setContextMenuPolicy(Qt.NoContextMenu)

        # keep references to make sure they don't get destroyed
        self.model = None
        self.handler = WebCallHandler()
        self.channel = QWebChannel()
        self.channel.registerObject('handler', self.handler)

        # connect to handler signals
        self.handler.chartReady.connect(self.chartReady)
        self.handler.dataChanged.connect(self.chartDataChanged)
        self.handler.layoutChanged.connect(self.chartLayoutChanged)
        self.handler.imageReady.connect(self.imageReady)

        # load react page and set web channel
        url = 'file://' + getResourcePath('react/index.html')
        self.load(QtCore.QUrl(url))
        self.page().setWebChannel(self.channel)


    def setModel(self, model):
        """
        Set the model and connect signals, but do not emit a data change event
        because a script evaluation will cause the data to update anyway.
        """
        self.model = model
        self.model.dataChanged.connect(self.dataChanged)
        # self.dataChanged()

    def dataChanged(self):
        """
        Model has changed
        """
        # only update if component has mounted
        if self.handler.editorHasMounted:
            data = copy.deepcopy(self.model.data)
            insertSourcesIntoTraces(data['data'], data['dataSources'])
            self.handler.updateChartState(data);


    def chartReady(self):
        """
        Chart has mounted on Javascript side, so update chart state
        """
        if self.model:
            self.dataChanged()


    def chartDataChanged(self, data):
        """
        Javascript signals model changes
        """
        # ignore model changed signal when change comes from the view
        with disconnectSignal(self.model.dataChanged, self.dataChanged):
            removeSourcesFromTraces(data)
            self.model.setChartData(data)


    def chartLayoutChanged(self, layout):
        """
        Javascript signals model changes
        """
        # ignore model changed signal when change comes from the view
        with disconnectSignal(self.model.dataChanged, self.dataChanged):
            cleanLayout(layout)
            self.model.setChartLayout(layout)


    def requestImage(self, callback, width=None, height=None):
        self.imageRequestCallbackQueue.put(callback)
        self.handler.requestImage(width, height)


    def imageReady(self, imageUrl):
        resp = urllib.request.urlopen(imageUrl)
        data = resp.file.read()
        self.imageRequestCallbackQueue.get()(data)

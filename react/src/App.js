import React, {Component} from 'react';
import plotly from 'plotly.js/dist/plotly';
import PlotlyEditor from 'react-chart-editor';
import 'react-chart-editor/lib/react-chart-editor.css';
import './App.css';


const DEBUG = 0;

function dlog(...args) {
  DEBUG && console.log(...args);
}

// default plotly configuration
const config = {
  editable: true,
  displaylogo: false,
  modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
};


class App extends Component {
  constructor() {
    super();
    this.handler = null;  // web call handler
    this.renderCount = 0;

    this.state = {        // react UI state
      data: [],           // chart trace data
      layout: {},         // chart layout data
      frames: [],         // chart animation data
      dataSources: {},    // editor source data
      ready: false        // ready to render app div
    };

    /*eslint-disable no-undef*/
    // setup web channel and bind to handler functions
    let self = this;
    new QWebChannel(window.qt.webChannelTransport, function(channel) {
      self.handler = channel.objects.handler;

      // store javascript to python calls
      self.emitDataChanged = (obj) => self.handler.dataChangedJson(JSON.stringify(obj));
      self.emitLayoutChanged = (obj) => self.handler.layoutChangedJson(JSON.stringify(obj));
      // self.emitDidMount = handler.chartDidMount;

      // observe python to javascript calls
      self.handler.updateChartStateSignal.connect(self.handleChartModelChanged.bind(self));
      self.handler.requestImageSignal.connect(self.handelImageRequest.bind(self));

      // signal that chart has mounted
      self.handler.chartDidMount();
    });
    /*eslint-enable no-undef*/
  }


  /**
   * Generate an image from the Plotly graph and send to
   * python via the emitImageReady handler slot.
   */
  handelImageRequest(width, height) {
    let graphDiv = document.getElementById('plotly-plot');
    width = width || graphDiv.clientWidth;
    height = height || graphDiv.clientHeight;

    let options = {format: 'png', width: width, height: height};
    plotly.toImage(graphDiv, options).then(
        dataUrl => this.handler.emitImageReady(dataUrl)
    );
  }

  handleChartModelChanged(jsn) {
    dlog('handleChartModelChanged', jsn);

    let state = JSON.parse(jsn);
    // create list of data source options
    state.dataSourceOptions = Object.keys(state.dataSources).map(
      k => ({value: k, label: k})
    );
    // ready to render and emit to handler
    state.ready = true;
    this.setState(state);
  }


  /**
   * Called after changes are made in the chart editor.
   */
  onEditorUpdate(data, layout, frames) {
    dlog('onEditorUpdate', data, layout)

    this.state.ready && this.emitDataChanged(data);
    this.setState({data, layout, frames});
  }

 /*
  * Called after the chart has been rendered
  * May be triggered by changes in editor or layout changes in the chart.
  */
  onChartRender(data, layout, frames) {
    dlog('onChartRender', data, layout)

    // plotly initially calls onRender twice so ignore the first one
    if (++this.renderCount == 1) return;

    // chart can change layout options such as view range
    this.state.ready && this.emitLayoutChanged(layout);
    this.state.ready && this.handler.emitChartUpdated()
  }

  render() {
    // don't render until we are ready to avoid gui flicker
    if (!this.state.ready) {
      return null;
    }

    return (
      <div className="App">
        <PlotlyEditor
          data={this.state.data}
          layout={this.state.layout}
          config={config}
          frames={this.state.frames}
          dataSources={this.state.dataSources}
          dataSourceOptions={this.state.dataSourceOptions}
          plotly={plotly}
          onUpdate={this.onEditorUpdate.bind(this)}
          onRender={this.onChartRender.bind(this)}
          divId='plotly-plot'
          useResizeHandler
          debug
          advancedTraceTypeSelector
        />
      </div>
    );
  }
}

export default App;

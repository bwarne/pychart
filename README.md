## PyChart - a python based chart design tool
![screenshot](assets/screenshots/sunburst.png)
PyChart integrates a Python scripting for data generation and the Plotly react-chart-editor for interactive chart design into a Qt based application.  It strives to ease the friction between data and display by leveraging Python scripting for data creation and manipulation and a user interface for the often difficult process of chart design and layout.

Download the [Release v0.1.0 for macOS](https://github.com/bwarne/pychart/releases/download/v0.1.0/PyChart-0.1.0.dmg)

### Features
* Fast script execution and interruption
* Export charts as PNG files or to the clipboard
* Run chart scripts from the command-line

### Run from the command-line
After creating and saving a PyChart file, the chart can be created and exported from the command-line:
```bash
./PyChart.app/Contents/MacOS/PyChart run /path/to/plot.cht /path/to/image.png --width 640 --height 480
```

### Using a Virtual Environment
A virtual environment can be activated by executing the activate_this.py file in your script:
```python
activate_this_file = "/path/to/virtualenv/bin/activate_this.py"
exec(open(activate_this_file).read(), dict(__file__=activate_this_file))
```

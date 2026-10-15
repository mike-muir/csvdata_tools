# csvdata_tools
Tools for exporting IADS to CSV and plotting CSV data

# MuirList.csv
This is a running csv list of variable names that I have found useful to plot from IADS data. It is meant to be used with [iads-export](https://github.com/merlinlabs/iads-export).
See also the Confluence page for a [tutorial](https://merlinlabs.atlassian.net/wiki/spaces/MSD/pages/1053327426/How+to+export+a+CSV+from+an+IADS+Data+Dictionary) on iads-export.

# iads_export_gui.py
A GUI that builds the manual export YAML file for [iads-export](https://github.com/merlinlabs/iads-export) and runs the export, so you don't have to edit the YAML or activate the virtual environment by hand. Run it with `python iads_export_gui.py`.
* Pick the data directory and time format, and add one or more exports (output CSV, data group file, start/stop time). Each option has a `?` button explaining it.
* The data group file can be an existing CSV, or **Build New...** launches `selectFromPrn.py` and fills in the CSV as soon as you save it there.
* **Save YAML** writes the file. Exports in the YAML file are loaded automatically the next time the GUI starts (or press **Load**).
* **Check parameters** runs `--check`, **Run Export** runs the export using the iads-export repo's `ie_venv`, and **Plot Output** opens the exported CSV in `plotcsv.py`.
* Settings (repo path, data directory, time format, YAML path) are remembered in `.iads_export_gui.json`. Set the iads-export repo folder in the GUI if it is not in the default location.

# selectFromPrn.py
This is a tool for loading and selecting a prn file. It was used to build MuirList.csv. It can load an existing prn for you to select data from. It can also load an existing csv (such as MuirList.csv) to edit/add/remove signals from the list. When ready, exporting to csv creates a file for us with [iads-export](https://github.com/merlinlabs/iads-export)

It can be launched by `iads_export_gui.py`, or run directly. With `--result-file <path>` it writes the path of each saved CSV to that file, which is how the GUI picks up the file you just saved.

# plotcsv.py
This is a python plotting tool. Assuming you have some CSV data (like csvs created with [iads-export](https://github.com/merlinlabs/iads-export)) this tool will load and allow you to search for and plot the data.

Selected variables can be assigned to numbered subplots (default is subplot 1; use the **Subplot #** box or right-click > Move to subplot) and the plot is split into as many subplots as you assign. Variables can also be moved to a right-hand axis. It can be launched by `iads_export_gui.py`, or run directly, with an optional argument for filepath: `python plotcsv.py <path-to-csv>`.

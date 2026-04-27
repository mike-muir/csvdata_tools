# csvdata_tools
Tools for exporting IADS to CSV and plotting CSV data

# MuirList.csv
This is a running csv list of variable names that I have found useful to plot from IADS data. It is meant to be used with [iads-export](https://github.com/merlinlabs/iads-export).
See also the Confluence page for a [tutorial](https://merlinlabs.atlassian.net/wiki/spaces/MSD/pages/1053327426/How+to+export+a+CSV+from+an+IADS+Data+Dictionary) on iads-export.

# selectFromPrn.py
This is a tool for loading and selecting a prn file. It was used to build MuirList.csv. It can load an existing prn for you to select data from. It can also load an existing csv (such as MuirList.csv) to edit/add/remove signals from the list. When ready, exporting to csv creates a file for us with [iads-export](https://github.com/merlinlabs/iads-export)

# plotcsv.py
This is a python plotting tool. Assuming you have some CSV data (like csvs created with [iads-export](https://github.com/merlinlabs/iads-export)) this tool will load and allow you to search for and plot the data.

# bitcraft-product-gradient
A tool to display geophysical distribution of trade prices for a given product in BitCraft Online.

In laymans terms, this tools drapes a sheet across the world in such a way that it's pinned above the highest buy orders and below the lowest sell orders of any given market. It does not take into account order quantity at all, and will fall down in the absence of buy orders to prop it up, or get stuck flat at a low value rather than getting sculpted if all the world's buy orders are lower than all the world's sell orders.

If unfamiliar with python and GitHub, to run the tool:
- Clone the project with GitHub, or by downloading the code as a zip file.
- Install a compatible Python version (only needs to be done once). The tool was written with 3.12.9, and was succesfully run with 3.13.6
- In a command line, run the command pip install poetry (only needs to be done once).
- Navigate the command line to the project directory.
- Run the command poetry install (only needs to be done on initial install, or after a project update).
- After setting the configs according to your preference, run the command poetry run python app/main.py

The operation of the tool is determined by the config.ini file.

[General] query_rate: How many seconds are paused after a Bitjita API query, out of courtesy and to avoid rate limits.

[Map] resolution: How many tiles wide and tall the map is calculated as. Larger values will dramatically slow down the tool.
[Map] N_contour: How many contour lines get drawn. Can be set to 0 to opt out of the contours.
[Map] plot_field: Allows one to opt out of the general scalar field colormapping.
[Map] plot_claims: Allows ont to opt in or out of displaying a given market's buy and sell orders.

[Target] item_type: Whether the item in question is a normal "item", or a "cargo".
[Target] item_id: ID value of the item in question. Most easily found on brico.app

On first use, the tool will run slowly as it saves locations of markets it hasn't seen before. On further uses, as fewer new markets are encountered, it will run substantially faster. If for some reason you wish to discard saved locations (perhaps there's some error), then you can delete saved_claim_locations.csv

As the tool runs, it will build a bc-gradient.log file. This can be used for debugging if the script fails.

As an output, the tool will save a full world map png in the outputs directory. Additionally, a maptlotlib window will pop up. This window can be be zoomed in or panned at will. If [Map] plot_field is set to True, then hovering over the map with your cursor will also display the calculated trade price (and the coordinates) at the position of your cursor. 
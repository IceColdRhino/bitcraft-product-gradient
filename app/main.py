import configparser
import logging
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
import requests
import scipy
import sys
import time

def main():
    logging.info("Reading Config file.")
    config = configparser.ConfigParser()
    config.read('config.ini')
    query_rate = config["General"]["query_rate"]
    query_rate = float(query_rate)

    res = config["Map"]["resolution"]
    res = int(res)
    N_contour = config["Map"]["N_contour"]
    N_contour = int(N_contour)
    plot_field = config["Map"]["plot_field"]
    plot_claims = config["Map"]["plot_claims"]

    item_type = config["Target"]["item_type"]
    item_id = config["Target"]["item_id"]

    logging.info("Initializing Bitjita API client.")
    data_client = bitjita_client()

    logging.info("Making Bitjita data query for target item.")
    target = data_client._make_request(f"market/{item_type}/{item_id}");    time.sleep(query_rate)
    target_name = target["item"]["name"]
    logging.info(f"Target product identified as {item_type}: {target_name}")
    buy_orders = target.get("buyOrders",[])
    sell_orders = target.get("sellOrders",[])

    # Hard-coded limits to the map edges (in "small hex" units)
    # "2560" seems to be the length/width of a single region in medium hex units
    x_max = 2560*3*3
    z_max = 2560*3*3

    logging.info("Initializing computational fields.")
    max_buy = np.zeros([res,res])
    min_sell = np.inf*int(1e6)*np.ones([res,res])
    try:
        loc_dict = {}
        loc_df = pd.read_csv("saved_claim_locations.csv", index_col=0)
        d = loc_df.to_dict("split")
        d = dict(zip(d["index"], d["data"]))
        for claim_id in d:
            loc_dict[str(claim_id)] = {"X":d[claim_id][0],"Z":d[claim_id][1]}
        logging.info("Succesfully loaded saved claim locations.")
    except:
        logging.warning("Unable to load saved claim locations.")
        loc_dict = {}

    logging.info("Parsing buy orders:")
    for i in range(0,len(buy_orders)):
        if i%100 == 0:
            logging.info(f"   {np.round(100*i/len(buy_orders),2)} % Complete - {i:,}/{len(buy_orders):,}")

        claim_id = buy_orders[i]["claimEntityId"]
        if claim_id not in loc_dict:
            logging.info(f"      Querying Bitjita for location of claim id {claim_id}: {buy_orders[i]["claimName"]}")
            try:
                claim = data_client._make_request(f"claims/{claim_id}")["claim"]; time.sleep(query_rate)
            except:
                logging.error("      Query failed, skipping claim.");   time.sleep(query_rate)
                continue
            loc_dict[claim_id] = {"X":claim["locationX"],"Z":claim["locationZ"]}
        x_ind = int(loc_dict[claim_id]["X"]*res/x_max)
        z_ind = int(loc_dict[claim_id]["Z"]*res/z_max)
        if max_buy[x_ind][z_ind] < int(buy_orders[i]["priceThreshold"]):
            max_buy[x_ind][z_ind] = int(buy_orders[i]["priceThreshold"])
    logging.info("Completed parsing buy orders.")

    logging.info("Parsing sell orders:")
    for i in range(0,len(sell_orders)):
        if i%100 == 0:
            logging.info(f"   {np.round(100*i/len(sell_orders),2)} % Complete - {i:,}/{len(sell_orders):,}")
        
        claim_id = sell_orders[i]["claimEntityId"]
        if claim_id not in loc_dict:
            logging.info(f"      Querying Bitjita for location of claim id {claim_id}: {sell_orders[i]["claimName"]}")
            try:
                claim = data_client._make_request(f"claims/{claim_id}")["claim"]; time.sleep(query_rate)
            except:
                logging.error("      Query failed, skipping claim.");   time.sleep(query_rate)
                continue
            loc_dict[claim_id] = {"X":claim["locationX"],"Z":claim["locationZ"]}
        x_ind = int(loc_dict[claim_id]["X"]*res/x_max)
        z_ind = int(loc_dict[claim_id]["Z"]*res/z_max)
        if min_sell[x_ind][z_ind] > int(sell_orders[i]["priceThreshold"]):
            min_sell[x_ind][z_ind] = int(sell_orders[i]["priceThreshold"])
    logging.info("Completed parsing sell orders.")

    logging.info("Saving claim locations to speed up future mapping.")
    loc_df = pd.DataFrame.from_dict(loc_dict,orient="index")
    loc_df.to_csv("saved_claim_locations.csv")

    logging.info("Calculating price scalar field.")
    for i in range(0,res):
        for j in range(0,res):
            if max_buy[i][j] > min_sell[i][j]:
                median = (max_buy[i][j] + min_sell[i][j])/2
                max_buy[i][j] = median
                min_sell[i][j] = median

    prices = max_buy.copy()
    old_prices = prices*10
    err = 1
    counter = 0
    while err>1e-32:
        counter += 1
        old_prices = prices.copy()
        if counter%1000 == 0:
            counter = 0
            try:
                logging.info(f"   Mapped Field Convergence: {np.round(100*(-np.log10(err))/32,2)} %")
            except:
                logging.info(f"   Mapped Field Convergence: 100.0 %")

        # Iterate the price scalar field to follow the laplace equation in the absence of market constraints
        # Brute force, hacky, inefficient. But it mostly works.
        prices += 0.1*scipy.ndimage.laplace(prices,mode="nearest")

        # Constrain the local prices to always be within the local buy-sell window
        prices = np.maximum(prices.copy(),max_buy.copy())
        prices = np.minimum(prices.copy(),min_sell.copy())

        # Difference between old and new prices fields
        err = np.max((prices-old_prices)**2)

    logging.info("Loading the world map.")
    img = np.array(Image.open("assets/map.png").convert('L'))

    logging.info("Performing necessary transforms and trims.")
    img = np.flip(img,axis=0)

    logging.info("Plotting the world map as the base layer.")
    fig, ax = plt.subplots(figsize=(6,6))

    imgplot = plt.imshow(img,origin="lower",extent=(0,7680,0,8867),cmap="Greys_r")

    X = np.linspace(0,x_max/3,res)
    Z = np.linspace(0,z_max/3,res)

    mesh_X, mesh_Z = np.meshgrid(X,Z)

    if plot_field == "True":
        logging.info("Plotting the price scalar field.")
        priceplot = ax.imshow(
            prices.T,
            origin="lower",
            extent=(0,7680,0,7680),
            alpha=0.5,
            cmap="bwr",
            )
        fig.colorbar(priceplot,ax=ax,shrink=0.8)
    else:
        logging.info("Omitting the price scalar field.")
    
    if N_contour!=0:
        logging.info("Plotting the price contours.")
        contplot = ax.contour(
            mesh_X,
            mesh_Z,
            prices.T,
            levels=N_contour,
            cmap="bwr",
            zorder=1,
            )
        ax.clabel(contplot, fontsize=8, colors="black")
    else:
        logging.info("Omitting the price contours.")

    if plot_claims == "True":
        logging.info("Plotting individual claim orders.")
        p_min = np.min(prices)
        p_max = np.max(prices)
        for claim_id in loc_dict:
            buys = [b for b in buy_orders if b["claimEntityId"]==claim_id]
            max_buy = 0
            for b  in buys:
                if int(b["priceThreshold"]) > max_buy:
                    max_buy = int(b["priceThreshold"])

            if max_buy == 0:
                continue

            plt.scatter(
                loc_dict[claim_id]["X"]/3,
                loc_dict[claim_id]["Z"]/3,
                marker=11,
                c=max_buy,
                cmap="bwr",
                vmin=p_min,
                vmax=p_max,
                s=5,
                zorder=2,
            )
                
            sells = [s for s in sell_orders if s["claimEntityId"]==claim_id]
            min_sell = np.inf
            for s  in sells:
                if int(s["priceThreshold"]) < min_sell:
                    min_sell = int(s["priceThreshold"])

            plt.scatter(
                loc_dict[claim_id]["X"]/3,
                loc_dict[claim_id]["Z"]/3,
                marker=10,
                c=min_sell,
                cmap="bwr",
                vmin=p_min,
                vmax=p_max,
                s=5,
                zorder=2,
            )
    else:
        logging.info("Omitting individual claim orders.")

    logging.info("Displaying full map.")
    plt.title(f"{target_name} Price Distribution")
    plt.xlim([0,7680])
    plt.ylim([0,7680])
    ax.get_xaxis().set_ticks([])
    ax.get_yaxis().set_ticks([])
    plt.tight_layout()
    plt.savefig(f"outputs/{target_name}.png",dpi=300,bbox_inches="tight")
    plt.show()

class bitjita_client():
    """
    A client class for making queries to the Bitjita public API.
    """
    def __init__(self):
        self.base_url = "https://bitjita.com/api"

    def _make_request(self,endpoint,params=None):
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(
                url=url,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Bitjita API Request failed: {e}")
            raise

if __name__ == "__main__":
    # Initialize logging to both console and log file
    logging.basicConfig(
        # level=logging.DEBUG,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bc-gradient.log", mode="w"),
        ],
        force=True,
    )
    logging.info("===== BitCraft Product Gradient Starting =====")
    main()
    logging.info("=== BitCraft Product Gradient Shutting Down ===")
    logging.shutdown()
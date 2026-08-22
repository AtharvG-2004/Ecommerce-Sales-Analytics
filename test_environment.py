from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parent
ORDERS_ITEMS_CSV = PROJECT_ROOT / "olist_order_items_dataset.csv"


def main():
    order_items = pd.read_csv(ORDERS_ITEMS_CSV, nrows=1000)
    print(f"pandas {pd.__version__}: SUCCESS - loaded {len(order_items)} order items")

    prices = np.array(order_items["price"].head(5), dtype=float)
    print(f"numpy {np.__version__}: SUCCESS - created array with shape {prices.shape}")

    plt.figure(figsize=(5, 3))
    plt.plot(prices, marker="o")
    plt.title("First five order item prices")
    plt.xlabel("Item")
    plt.ylabel("Price")
    plt.tight_layout()
    plt.close()
    print(f"matplotlib {matplotlib.__version__}: SUCCESS - rendered a line chart")

    plt.figure(figsize=(5, 3))
    sns.histplot(data=order_items, x="price", bins=10)
    plt.title("Order item price distribution")
    plt.tight_layout()
    plt.close()
    print(f"seaborn {sns.__version__}: SUCCESS - rendered a distribution chart")

    print("Environment check completed successfully.")


if __name__ == "__main__":
    main()

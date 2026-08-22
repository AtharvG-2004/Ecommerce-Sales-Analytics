from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
order_items = pd.read_csv(PROJECT_ROOT / "olist_order_items_dataset.csv", nrows=1000)

st.set_page_config(page_title="Environment Check", layout="centered")
st.title("Environment Check")
st.dataframe(order_items.head(10), use_container_width=True)

figure, axis = plt.subplots(figsize=(7, 4))
sns.histplot(data=order_items, x="price", bins=20, ax=axis)
axis.set_title("Order item price distribution")
axis.set_xlabel("Price")
st.pyplot(figure)

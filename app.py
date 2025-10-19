from flask import Flask, jsonify, render_template
import os

import time
import pickle
import pandas as pd
import requests
import glob
import json
import re
import io
import openpyxl
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for Flask
from flask import Response, jsonify

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium_session import selenium_session
from cache import cache_data, get_cached_data

# # from download import download_excel
# from download import download_bp
# from screener_view import get_screener_view
# from screener_data import process_screener_data

from selenium import webdriver
import sys
app = Flask(__name__)

@app.route('/')
def hello():
    return "Welcome to Janet's Project"

@app.route('/about')
def about():
    return "This project is about learning Flask and Git repository."
from flask import request
@app.route('/scrape/<string:symbol>')
def scrape(symbol):
    """Scrapes all financial ratios from Screener.in for the given symbol and returns JSON with optional cache override."""
    
    refresh = request.args.get("refresh", "false").lower() == "true"
    cache_key = f"ratios:{symbol}"

    # ⚠️ Use cached data unless 'refresh=true' is explicitly passed
    if not refresh:
        cached_data = get_cached_data(cache_key)
        if cached_data:
            return jsonify({"symbol": symbol, "ratios": cached_data})

    browser = selenium_session.get_browser()

    # 🔐 Optional: Login if required (as discussed earlier)
    # browser.get("https://www.screener.in/login/")
    # [insert login logic here if needed]

    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    browser.get(url)
    browser.execute_script("window.scrollTo(0, 400)")
    time.sleep(5)  # JS ratios usually lazy-load

    try:
        # Wait for the section to load (either type)
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul#top-ratios li'))
        )
        time.sleep(1)  # Optional: Give extra time for JS to render

        # Initialize dictionary
        ratios_data = {}

        # ✅ Get all ratio rows (default + quick-ratio)
        ratio_elements = browser.find_elements(By.CSS_SELECTOR, 'ul#top-ratios li')

        print(f"Found {len(ratio_elements)} total ratios")

        for item in ratio_elements:
            try:
                # Extract label and value
                key = item.find_element(By.CSS_SELECTOR, "span.name").text.strip()
                value = item.find_element(By.CSS_SELECTOR, "span.nowrap span.number").text.strip()
                ratios_data[key] = value
            except Exception as e:
                print(f"⚠️ Skipping ratio due to: {e}")
                continue

        if not ratios_data:
            return jsonify({"error": "No ratios found. DOM may have changed."})

        # ✅ Save new data to cache
        cache_data(cache_key, ratios_data)

        return jsonify({"symbol": symbol, "ratios": ratios_data})

    except Exception as e:
        return jsonify({"error": f"Failed to scrape {symbol}: {str(e)}"})

# **📌 Endpoint: `/nseid/<SYMBOL>`**
@app.route('/nseid/<string:symbol>')
def fetch_chart_data(symbol):
    """Fetches Screener chart data with caching."""
    cache_key = f"chart:{symbol}"
    cached_data = get_cached_data(cache_key)

    if cached_data:
        return jsonify(cached_data)  # Return cached result

    browser = selenium_session.get_browser()
    browser.get(f'https://www.screener.in/company/{symbol}/')

    try:
        company_id_data = browser.find_element(By.XPATH, '//a[contains(@href,"/quarter/")]')
        company_url = company_id_data.get_attribute('href')

        m = re.search('quarter/([A-Za-z_0-9.-]+).*', company_url)
        if m:
            chart_id = m.group(1)
            r = requests.get(f"https://www.screener.in/api/company/{chart_id}/chart/?q=Price-DMA50-DMA200-Volume&days=365&consolidated=true")
            chart_data = r.json()

            result = {"symbol": symbol, "chart_id": chart_id, "chart_data": chart_data}
            cache_data(cache_key, result)  # Cache result for reuse
            return jsonify(result)
        else:
            return jsonify({"error": "Company ID not found, structure may have changed."})

    except Exception as e:
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"})
    
@app.route('/chart/<string:symbol>')
def chart(symbol):
    """Renders an annotated chart with Buy/Sell markers based on DMA crossovers."""
    r = requests.get(f'http://localhost:5000/nseid/{symbol}')
    if r.status_code != 200:
        return jsonify({"error": f"Failed to fetch chart data for {symbol}"}), 500
    
    data = r.json().get("chart_data", {})
    datasets = data.get("datasets", [])
    if not datasets:
        return jsonify({"error": "No datasets found."}), 404

    price_data = next(
    d["values"] for d in datasets if d["label"] in ["Price on NSE", "Price on BSE"]
    )
    dma50_data = next(d["values"] for d in datasets if d["label"] == "50 DMA")
    dma200_data = next(d["values"] for d in datasets if d["label"] == "200 DMA")
    volume_data = next(d["values"] for d in datasets if d["label"] == "Volume")

    # Convert to DataFrame
    df_price = pd.DataFrame(price_data, columns=["Date", "Price"])
    df_price["Date"] = pd.to_datetime(df_price["Date"])
    df_price["Price"] = df_price["Price"].astype(float)

    df_dma50 = pd.DataFrame(dma50_data, columns=["Date", "DMA50"])
    df_dma50["Date"] = pd.to_datetime(df_dma50["Date"])
    df_dma50["DMA50"] = df_dma50["DMA50"].astype(float)

    df_dma200 = pd.DataFrame(dma200_data, columns=["Date", "DMA200"])
    df_dma200["Date"] = pd.to_datetime(df_dma200["Date"])
    df_dma200["DMA200"] = df_dma200["DMA200"].astype(float)

    df_volume = pd.DataFrame(volume_data, columns=["Date", "Volume", "Meta"])
    df_volume["Date"] = pd.to_datetime(df_volume["Date"])
    df_volume["Volume"] = df_volume["Volume"].astype(int)

    df = df_price.merge(df_dma50, on="Date").merge(df_dma200, on="Date").merge(df_volume, on="Date")

    # Detect buy/sell signals based on crossings
    df["prev_price"] = df["Price"].shift(1)
    df["prev_dma50"] = df["DMA50"].shift(1)
    df["prev_dma200"] = df["DMA200"].shift(1)

    # Short-term buy/sell
    df["buy_signal"] = (df["prev_price"] < df["prev_dma50"]) & (df["Price"] > df["DMA50"])
    df["sell_signal"] = (df["prev_price"] > df["prev_dma50"]) & (df["Price"] < df["DMA50"])

    # Long-term crossovers
    df["golden_cross"] = (df["prev_dma50"] < df["prev_dma200"]) & (df["DMA50"] > df["DMA200"])
    df["death_cross"] = (df["prev_dma50"] > df["prev_dma200"]) & (df["DMA50"] < df["DMA200"])

    # Plot
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(df["Date"], df["Price"], label="Price", color="blue", linewidth=2)
    ax1.plot(df["Date"], df["DMA50"], label="50 DMA", color="orange", linestyle="--")
    ax1.plot(df["Date"], df["DMA200"], label="200 DMA", color="red", linestyle="--")

    # Mark buy/sell points
    ax1.scatter(df.loc[df["buy_signal"], "Date"], df.loc[df["buy_signal"], "Price"],
                marker="^", color="green", s=100, label="Buy Signal")
    ax1.scatter(df.loc[df["sell_signal"], "Date"], df.loc[df["sell_signal"], "Price"],
                marker="v", color="red", s=100, label="Sell Signal")

    # Mark golden/death crosses
    ax1.scatter(df.loc[df["golden_cross"], "Date"], df.loc[df["golden_cross"], "DMA50"],
                marker="^", color="lime", s=200, edgecolor="black", label="Golden Cross")
    ax1.scatter(df.loc[df["death_cross"], "Date"], df.loc[df["death_cross"], "DMA50"],
                marker="v", color="darkred", s=200, edgecolor="black", label="Death Cross")

    ax1.set_ylabel("Price (₹)")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.4)

    ax2 = ax1.twinx()
    ax2.bar(df["Date"], df["Volume"], color="blue", alpha=0.5)
    ax2.set_ylabel("Volume", color="gray")

    plt.title(f"{symbol.upper()} — Price, 50/200DMA, Buy/Sell Markers")
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img.seek(0)
    return Response(img.getvalue(), mimetype="image/png")

if __name__ == '__main__':
    app.run(debug=True)



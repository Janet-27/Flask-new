from flask import Flask, jsonify, render_template
import os
import numpy as np
import time
import pickle
import base64
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
import smtplib, ssl
matplotlib.use('Agg')  # Use non-interactive backend for Flask
from flask import Response, jsonify, render_template

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

def send_email(subject, body, to_addrs=None):
    """Send email notifications via Gmail SMTP to multiple recipients."""
    import smtplib, ssl

    sender_email = "deepan.antony@gmail.com"
    password = "mohzxqmoeiisouxn"  # Gmail App Password (16-char)

    # ✅ Always include both recipients by default
    if to_addrs is None:
        to_addrs = [
            "mike.bmails@gmail.com",
            "janetfernando9@gmail.com"
        ]

    message = f"Subject: {subject}\n\n{body}"

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.set_debuglevel(1)
            server.starttls(context=ssl.create_default_context())
            server.login(sender_email, password)
            server.sendmail(sender_email, to_addrs, message.encode("utf-8"))

        print(f"✅ Email sent successfully to: {', '.join(to_addrs)}")

    except Exception as e:
        print(f"❌ Email failed: {e}")


# def send_email(subject, body, to_addrs=None):
#     """Sends an email notification using Gmail SMTP."""
#     sender_email = "deepan.antony@gmail.com"        # 🔹 your sender address
#     password = "mohzxqmoeiisouxn"                   # 🔹 your app-password (not Gmail password!)
#     if to_addrs is None:
#         to_addrs = ["mike.bmails@gmail.com","janetfernando9@gmail.com"]        # 🔹 default recipients

#     smtp_server = "smtp.gmail.com"
#     port = 587
#     context = ssl.create_default_context()

#     message = f"Subject: {subject}\n\n{body}"
#     try:
#         with smtplib.SMTP(smtp_server, port) as server:
#             server.starttls(context=context)
#             server.login(sender_email, password)
#             server.sendmail(sender_email, to_addrs, message.encode("utf-8"))
#         print(f"📧 Email sent successfully to {to_addrs}")
#     except Exception as e:
#         print(f"⚠️ Email failed: {e}")

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
            # r = requests.get(f"https://www.screener.in/api/company/{chart_id}/chart/?q=Price-DMA50-DMA200-Volume&days=180&consolidated=true")
            days = request.args.get("days", "365")
            url = f"https://www.screener.in/api/company/{chart_id}/chart/?q=Price-DMA50-DMA200-Volume&days={days}&consolidated=true"
            r = requests.get(url)
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
                marker="^", color="black", s=200, edgecolor="black", label="Golden Cross")
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

@app.route('/identifytrend/<string:symbol>')
def identify_trend(symbol):
    """
    Identifies Accumulation, Uptrend, Distribution, and Decline stages
    based on 50DMA vs 200DMA crossovers and slope behaviour.
    Returns both a color-coded chart and a textual summary (JSON).
    """
    # --- Fetch chart data from cache or Screener API ---
    # r = requests.get(f'http://localhost:5000/nseid/{symbol}')
    days = request.args.get("days", "365")
    r = requests.get(f'http://localhost:5000/nseid/{symbol}?days={days}')
    if r.status_code != 200:
        return jsonify({"error": f"Failed to fetch chart data for {symbol}"}), 500

    data = r.json().get("chart_data", {})
    datasets = data.get("datasets", [])
    if not datasets:
        return jsonify({"error": "No datasets found."}), 404

    # --- Extract core datasets ---
    price_data = next(
        d["values"] for d in datasets if d["label"] in ["Price on NSE", "Price on BSE"]
    )
    dma50_data = next(d["values"] for d in datasets if d["label"] == "50 DMA")
    dma200_data = next(d["values"] for d in datasets if d["label"] == "200 DMA")

    # --- Build DataFrame ---
    df = pd.DataFrame(price_data, columns=["Date", "Price"])
    df["Date"] = pd.to_datetime(df["Date"])
    df["Price"] = df["Price"].astype(float)

    df["DMA50"] = [float(v[1]) for v in dma50_data]
    df["DMA200"] = [float(v[1]) for v in dma200_data]

    # --- Compute slopes to identify direction ---
    df["DMA50_slope"] = df["DMA50"].diff()
    df["DMA200_slope"] = df["DMA200"].diff()

    # --- Define stage logic ---
    conditions = [
        (df["DMA50"] < df["DMA200"]) & (df["DMA50_slope"] > 0),  # Accumulation
        (df["DMA50"] > df["DMA200"]) & (df["DMA50_slope"] > 0),  # Uptrend
        (df["DMA50"] > df["DMA200"]) & (df["DMA50_slope"] < 0),  # Distribution
        (df["DMA50"] < df["DMA200"]) & (df["DMA50_slope"] < 0),  # Decline
    ]
    choices = [
        "Stage 1 - Accumulation",
        "Stage 2 - Uptrend",
        "Stage 3 - Distribution",
        "Stage 4 - Decline",
    ]
    df["Stage"] = np.select(conditions, choices, default=None)

    # --- Identify latest and previous stage ---
    stage_changes = (
        df.loc[df["Stage"].shift() != df["Stage"], ["Date", "Stage"]]
        .dropna()
        .reset_index(drop=True)
    )

    if not stage_changes.empty:
        latest_stage = stage_changes["Stage"].iloc[-1]
        last_change_date = stage_changes["Date"].iloc[-1]

        # 🩵 FIX: Make sure we have a fallback if only one stage exists
        if len(stage_changes) > 1:
            previous_stage = stage_changes["Stage"].iloc[-2]
        else:
            # fallback to earliest available stage if only one stage detected
            first_stage = df["Stage"].dropna().iloc[0] if not df["Stage"].dropna().empty else "Unknown"
            previous_stage = first_stage if first_stage != latest_stage else "No previous stage in selected range"
    else:
        latest_stage = "Unknown"
        last_change_date = "N/A"
        previous_stage = "Unknown"
        # --- Determine trade eligibility ---
    if latest_stage.startswith("Stage 2") and previous_stage.startswith("Stage 1"):
        eligibility = "✅ Yes — In Uptrend after Accumulation"
    else:
        eligibility = "❌ No — Fails Stage Sequence Rule"


    # --- Summarize trend durations ---
    stage_summary = (
        df.groupby("Stage")["Date"]
        .agg(["min", "max"])
        .dropna()
        .reset_index()
        .rename(columns={"min": "Start", "max": "End"})
    )
    stage_summary["Duration_days"] = (stage_summary["End"] - stage_summary["Start"]).dt.days

    # --- Plot chart with shaded backgrounds ---
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(df["Date"], df["Price"], color="blue", label="Price", linewidth=2)
    ax1.plot(df["Date"], df["DMA50"], color="orange", linestyle="--", label="50 DMA")
    ax1.plot(df["Date"], df["DMA200"], color="red", linestyle="--", label="200 DMA")

    stage_colors = {
        "Stage 1 - Accumulation": "#aaffaa",
        "Stage 2 - Uptrend": "#b0e0ff",
        "Stage 3 - Distribution": "#ffe066",
        "Stage 4 - Decline": "#ff9999",
    }

    current_stage = None
    start_idx = 0
    for i in range(1, len(df)):
        stage = df["Stage"].iloc[i]
        if stage != current_stage:
            if current_stage is not None:
                color = stage_colors.get(current_stage, "#dddddd")
                ax1.axvspan(df["Date"].iloc[start_idx], df["Date"].iloc[i],
                            color=color, alpha=0.2)
            current_stage = stage
            start_idx = i
    if current_stage is not None:
        color = stage_colors.get(current_stage, "#dddddd")
        ax1.axvspan(df["Date"].iloc[start_idx], df["Date"].iloc[-1],
                    color=color, alpha=0.2)

    ax1.legend(loc="upper left")
    ax1.set_ylabel("Price (₹)")
    ax1.grid(alpha=0.4)
    plt.title(f"{symbol.upper()} — Stage Analysis (Current: {latest_stage})")
    plt.tight_layout()

    # --- Convert to image bytes ---
    img = BytesIO()
    plt.savefig(img, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img.seek(0)

    # --- Format last change date ---
    try:
        formatted_date = pd.to_datetime(last_change_date).strftime("%Y - %b - %d")
    except Exception:
        formatted_date = "N/A"


    # --- Send email if new stage is detected ---
    try:
        subject = f"{symbol.upper()} Stage Update: {latest_stage}"
        body = (
            f"Symbol: {symbol.upper()}\n"
            f"Current Stage: {latest_stage}\n"
            f"Previous Stage: {previous_stage}\n"
            f"Last Change Date: {formatted_date}\n\n"
            "Visit dashboard for full chart view:\n"
            f"http://localhost:5000/trendview/{symbol}"
        )
        print(f"📬 Checking if email should be sent for {symbol}...")
        try:
            subject = f"{symbol.upper()} Stage Update: {latest_stage}"
            body = (
                f"Symbol: {symbol.upper()}\n"
                f"Current Stage: {latest_stage}\n"
                f"Previous Stage: {previous_stage}\n"
                f"Last Change Date: {formatted_date}\n\n"
                "Visit dashboard for full chart view:\n"
                f"http://localhost:5000/trendview/{symbol}"
            )

            # # 🔹 Force-send for testing
            # print("📧 Forcing email send for test...")
            # send_email(subject, body)

        except Exception as e:
            print(f"⚠️ Notification skipped: {e}")
        # ✅ Send only if stage changed recently (within last few days)
        if isinstance(last_change_date, pd.Timestamp):
            delta_days = (pd.Timestamp.now() - last_change_date).days
            if delta_days <= 2:  # avoid daily spam; change threshold as needed
                send_email(subject, body)
    except Exception as e:
        print(f"⚠️ Notification skipped: {e}")

    # --- Build JSON summary ---
    summary = {
        "symbol": symbol.upper(),
        "current_stage": latest_stage,
        "previous_stage": previous_stage,
        "last_change_date": formatted_date,
        "stage_durations": stage_summary.to_dict(orient="records"),
        "eligibility_for_trade": eligibility,
    }
    summary["eligibility_for_trade"] = eligibility


    # --- Return both JSON + Image ---
    # Flask doesn’t support multiple body types directly, so return multipart or base64
    encoded_img = base64.b64encode(img.getvalue()).decode("utf-8")
    summary["chart_base64"] = f"data:image/png;base64,{encoded_img}"

    return jsonify(summary)

@app.route('/dashboard/<string:symbol>')
def dashboard(symbol):
    """
    Unified, styled dashboard for Trend + Backtest + Summary
    """
    days = request.args.get("days", "365")

    trend_resp = requests.get(f"http://localhost:5000/identifytrend/{symbol}?days={days}")
    backtest_resp = requests.get(f"http://localhost:5000/backtest/{symbol}?days={days}")

    if trend_resp.status_code != 200 or backtest_resp.status_code != 200:
        return f"<h3>❌ Failed to fetch data for {symbol}</h3>", 500

    trend = trend_resp.json()
    backtest = backtest_resp.json()

    eligibility = trend.get("eligibility_for_trade", "")
    badge_color = "green" if "✅" in eligibility else "red"

    html = f"""
    <html>
    <head>
      <title>{symbol.upper()} — Stock Analyzer Dashboard</title>
      <style>
        body {{
          font-family: 'Segoe UI', sans-serif;
          background: #f3f6fb;
          margin: 0;
        }}
        header {{
          background: #004080;
          color: white;
          padding: 15px 25px;
          font-size: 22px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        header button {{
          background: #007bff;
          color: white;
          border: none;
          padding: 8px 15px;
          border-radius: 6px;
          cursor: pointer;
        }}
        header button:hover {{ background: #005dc1; }}
        .tabs {{
          display: flex;
          background: #003366;
        }}
        .tab {{
          flex: 1;
          text-align: center;
          padding: 15px;
          cursor: pointer;
          color: white;
          font-weight: bold;
          transition: background 0.3s;
        }}
        .tab:hover {{ background: #0055aa; }}
        .tab.active {{ background: #007bff; }}
        .content {{ padding: 25px; }}
        .hidden {{ display: none; }}
        .card {{
          background: white;
          border-radius: 10px;
          box-shadow: 0 0 8px rgba(0,0,0,0.1);
          padding: 15px 20px;
          margin-bottom: 20px;
        }}
        .metric-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
        }}
        .metric {{
          text-align: center;
          padding: 15px;
          border-radius: 10px;
          color: white;
          font-size: 18px;
          font-weight: bold;
        }}
        .green {{ background: #28a745; }}
        .red {{ background: #dc3545; }}
        .blue {{ background: #007bff; }}
        .orange {{ background: #fd7e14; }}
        table {{
          border-collapse: collapse;
          width: 100%;
          background: white;
          border-radius: 10px;
          overflow: hidden;
        }}
        th, td {{
          border: 1px solid #ddd;
          padding: 8px;
          text-align: center;
        }}
        th {{ background: #e9f0ff; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr.profit td {{ color: #28a745; font-weight: bold; }}
        tr.loss td {{ color: #dc3545; }}
        img {{
          border-radius: 10px;
          box-shadow: 0 0 10px rgba(0,0,0,0.2);
          margin-top: 20px;
          max-width: 100%;
        }}
      </style>
      <script>
        function switchTab(tab) {{
          document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
          document.querySelectorAll('.section').forEach(s=>s.classList.add('hidden'));
          document.getElementById(tab+'Tab').classList.add('active');
          document.getElementById(tab+'Section').classList.remove('hidden');
        }}
        function reloadPage() {{
          location.reload();
        }}
      </script>
    </head>
    <body onload="switchTab('trend')">
      <header>
        <div><b>{symbol.upper()}</b> — {days}-day Dashboard</div>
        <button onclick="reloadPage()">⟳ Refresh</button>
      </header>

      <div class="tabs">
        <div id="trendTab" class="tab" onclick="switchTab('trend')">📈 Trend</div>
        <div id="backtestTab" class="tab" onclick="switchTab('backtest')">💹 Backtest</div>
        <div id="summaryTab" class="tab" onclick="switchTab('summary')">📊 Summary</div>
      </div>

      <div class="content">
        <!-- Trend Section -->
        <div id="trendSection" class="section">
          <div class="card">
            <h2>Trend Analysis — {trend.get('symbol')}</h2>
            <p><b>Current Stage:</b> {trend.get('current_stage')}<br>
               <b>Previous Stage:</b> {trend.get('previous_stage')}<br>
               <b>Last Change:</b> {trend.get('last_change_date')}<br>
               <b>Eligibility:</b> <span style="color:{badge_color}; font-weight:bold;">{eligibility}</span></p>
            <img src="{trend.get('chart_base64')}" />
          </div>
        </div>

        <!-- Backtest Section -->
        <div id="backtestSection" class="section hidden">
          <div class="card">
            <h2>Backtest Results — {backtest.get('symbol')}</h2>
            <div class="metric-grid">
              <div class="metric blue">Total Trades<br>{backtest.get('total_trades')}</div>
              <div class="metric green">Win Rate<br>{backtest.get('win_rate_percent')}%</div>
              <div class="metric orange">Avg Gain<br>{backtest.get('avg_gain_percent')}%</div>
              <div class="metric red">Total Return<br>{backtest.get('total_return_percent')}%</div>
            </div>
            <h3 style="margin-top:25px;">Trade History</h3>
            <table>
              <tr><th>Buy Date</th><th>Buy Price</th><th>Sell Date</th><th>Sell Price</th><th>Gain %</th></tr>
    """

    # ✅ Build table rows
    trades = backtest.get("trades", [])
    if trades:
        for t in trades:
            css_class = "profit" if t['gain_percent'] > 0 else "loss"
            html += f"<tr class='{css_class}'><td>{t['buy_date']}</td><td>{t['buy_price']}</td><td>{t['sell_date']}</td><td>{t['sell_price']}</td><td>{t['gain_percent']}</td></tr>"
    else:
        html += "<tr><td colspan='5'>No completed trades</td></tr>"

    html += f"""
            </table>
            <img src="{backtest.get('chart_base64')}" />
          </div>
        </div>

        <!-- Summary Section -->
        <div id="summarySection" class="section hidden">
          <div class="card">
            <h2>Quick Summary</h2>
            <p><b>Symbol:</b> {symbol.upper()}<br>
               <b>Days:</b> {days}<br>
               <b>Stage:</b> {trend.get('current_stage')}<br>
               <b>Eligibility:</b> {eligibility}<br>
               <b>Total Trades:</b> {backtest.get('total_trades')}<br>
               <b>Win Rate:</b> {backtest.get('win_rate_percent')}%<br>
               <b>Total Return:</b> {backtest.get('total_return_percent')}%</p>
            <img src="{backtest.get('trend_chart')}" />
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html



@app.route('/backtest/<string:symbol>')
def backtest(symbol):
    """Backtest Buy/Sell signals (DMA50 crossovers) and produce performance metrics."""
    days = request.args.get("days", "365")

    # --- Fetch chart data ---
    r = requests.get(f'http://localhost:5000/nseid/{symbol}?days={days}')
    if r.status_code != 200:
        return jsonify({"error": f"Failed to fetch chart data for {symbol}"}), 500
    data = r.json().get("chart_data", {})
    datasets = data.get("datasets", [])
    if not datasets:
        return jsonify({"error": "No datasets found."}), 404

    # --- Build DataFrame ---
    price_data = next(d["values"] for d in datasets if d["label"] in ["Price on NSE", "Price on BSE"])
    dma50_data = next(d["values"] for d in datasets if d["label"] == "50 DMA")
    dma200_data = next(d["values"] for d in datasets if d["label"] == "200 DMA")

    df = pd.DataFrame(price_data, columns=["Date", "Price"])
    df["Date"] = pd.to_datetime(df["Date"])
    df["Price"] = df["Price"].astype(float)
    df["DMA50"] = [float(v[1]) for v in dma50_data]
    df["DMA200"] = [float(v[1]) for v in dma200_data]

    # --- Detect Buy/Sell Signals ---
    df["prev_price"] = df["Price"].shift(1)
    df["prev_dma50"] = df["DMA50"].shift(1)
    df["buy_signal"] = (df["prev_price"] < df["prev_dma50"]) & (df["Price"] > df["DMA50"])
    df["sell_signal"] = (df["prev_price"] > df["prev_dma50"]) & (df["Price"] < df["DMA50"])

    buys = df.loc[df["buy_signal"], ["Date", "Price"]].reset_index(drop=True)
    sells = df.loc[df["sell_signal"], ["Date", "Price"]].reset_index(drop=True)

    # --- Pair Trades + Build Equity Curve ---
    trades, equity_curve = [], []
    balance = 1.0
    for i in range(len(buys)):
        buy_date, buy_price = buys.iloc[i]["Date"], buys.iloc[i]["Price"]
        sell = sells[sells["Date"] > buy_date].head(1)
        if sell.empty:
            continue
        sell_date, sell_price = sell.iloc[0]["Date"], sell.iloc[0]["Price"]
        gain = ((sell_price - buy_price) / buy_price)
        balance *= (1 + gain)
        trades.append({
            "buy_date": buy_date.strftime("%Y-%m-%d"),
            "buy_price": round(buy_price, 2),
            "sell_date": sell_date.strftime("%Y-%m-%d"),
            "sell_price": round(sell_price, 2),
            "gain_percent": round(gain * 100, 2)
        })
        equity_curve.append({"Date": sell_date, "Balance": balance})

    # --- Performance Stats ---
    total_buys, total_sells = len(buys), len(sells)
    total_trades = len(trades)
    win_trades = len([t for t in trades if t["gain_percent"] > 0])
    avg_gain = np.mean([t["gain_percent"] for t in trades]) if trades else 0
    total_return = (balance - 1) * 100 if trades else 0
    win_rate = (win_trades / total_trades * 100) if total_trades else 0

    # --- Stage info from identifytrend ---
    stage_data = requests.get(f"http://localhost:5000/identifytrend/{symbol}?days={days}")
    if stage_data.status_code == 200:
        s = stage_data.json()
        current_stage, previous_stage = s.get("current_stage", ""), s.get("previous_stage", "")
        eligibility = s.get("eligibility_for_trade", "")
        trend_chart = s.get("chart_base64", "")
    else:
        current_stage = previous_stage = eligibility = "N/A"
        trend_chart = ""

    # --- Plot Chart ---
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df["Date"], df["Price"], color="blue", label="Price")
    ax.plot(df["Date"], df["DMA50"], color="orange", linestyle="--", label="50 DMA")
    ax.plot(df["Date"], df["DMA200"], color="red", linestyle="--", label="200 DMA")
    ax.scatter(buys["Date"], buys["Price"], marker="^", color="green", s=100, label="Buy")
    ax.scatter(sells["Date"], sells["Price"], marker="v", color="red", s=100, label="Sell")
    ax.set_title(f"{symbol.upper()} — Backtest ({days} days)")
    ax.legend(loc="upper left"); ax.grid(alpha=0.4)
    if equity_curve:
        eq = pd.DataFrame(equity_curve)
        ax2 = ax.twinx()
        ax2.plot(eq["Date"], eq["Balance"], color="purple", label="Equity", linewidth=2)
        ax2.legend(loc="upper right"); ax2.set_ylabel("Equity (× start)")
    plt.tight_layout()
    img = BytesIO(); plt.savefig(img, format="png", dpi=150); plt.close(fig); img.seek(0)
    encoded_img = base64.b64encode(img.getvalue()).decode("utf-8")

    # --- Response JSON ---
    return jsonify({
        "symbol": symbol.upper(),
        "total_buys": total_buys,
        "total_sells": total_sells,
        "total_trades": total_trades,
        "win_rate_percent": round(win_rate, 2),
        "avg_gain_percent": round(avg_gain, 2),
        "total_return_percent": round(total_return, 2),
        "current_stage": current_stage,
        "previous_stage": previous_stage,
        "eligibility_for_trade": eligibility,
        "chart_base64": f"data:image/png;base64,{encoded_img}",
        "trend_chart": trend_chart,
        "trades": trades
    })



@app.route('/trendview/<string:symbol>')
def trendview(symbol):
    """
    Browser-friendly HTML dashboard for trend visualization.
    Fetches JSON from /identifytrend/<symbol> and renders an HTML summary.
    """
    # r = requests.get(f'http://localhost:5000/identifytrend/{symbol}')
    days = request.args.get("days", "365")
    r = requests.get(f'http://localhost:5000/identifytrend/{symbol}?days={days}')
    if r.status_code != 200:
        return f"<h2>Failed to fetch trend data for {symbol}</h2>", 500

    data = r.json()
    return render_template(
        "trend_view.html",
        symbol=data.get("symbol"),
        current_stage=data.get("current_stage"),
        previous_stage=data.get("previous_stage"),
        last_change_date=data.get("last_change_date"),
        stage_durations=data.get("stage_durations", []),
        trend_data=json.dumps(data)
    )

@app.route('/sendtestemail')
def send_test_email():
    """Manually trigger a test email to all recipients."""
    subject = "📊 Test Notification — Flask Trend Analyzer"
    body = (
        "Hello,\n\n"
        "This is a test notification from your Stock Trend Analyzer app.\n"
        "If you're seeing this, email delivery is working for all configured recipients.\n\n"
        "Regards,\n"
        "Flask Trend Analyzer"
    )
    send_email(subject, body)
    return "✅ Test email sent! Check both inboxes."

if __name__ == '__main__':
    app.run(debug=True)



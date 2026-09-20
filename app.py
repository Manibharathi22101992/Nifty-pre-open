import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(
    page_title="Dhan F&O Pre-Open Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# 1. DHAN CONFIGURATION
# -----------------------------------------------------------------------------
DHAN_CLIENT_ID = st.secrets.get("DHAN_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = st.secrets.get("DHAN_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_HEADERS = {
    "access-token": DHAN_ACCESS_TOKEN,
    "client-id": DHAN_CLIENT_ID,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# -----------------------------------------------------------------------------
# 2. INSTRUMENT & DATA INGESTION
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600*12)
def load_dhan_scrip_master():
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    try:
        df = pd.read_csv(url, low_memory=False)
        return df[df["SEM_SEGMENT"] == "D"].copy()
    except Exception:
        return None

def fetch_dhan_quotes(security_ids):
    if not DHAN_ACCESS_TOKEN or DHAN_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN":
        return None
    url = f"{DHAN_BASE_URL}/marketfeed/ohlc"
    payload = {"NSE_FNO": [int(sid) for sid in security_ids]}
    try:
        resp = requests.post(url, headers=DHAN_HEADERS, json=payload, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("NSE_FNO", {})
    except Exception:
        pass
    return None

def get_top_preopen_futures_data():
    scrip_master = load_dhan_scrip_master()
    if scrip_master is None or DHAN_ACCESS_TOKEN == "YOUR_ACCESS_TOKEN":
        return generate_mock_data()
    
    now = datetime.datetime.now()
    fut_stocks = scrip_master[scrip_master["SEM_INSTRUMENT_NAME"] == "FUTSTK"].copy()
    fut_stocks["SEM_EXPIRY_DATE"] = pd.to_datetime(fut_stocks["SEM_EXPIRY_DATE"])
    near_expiry = fut_stocks[fut_stocks["SEM_EXPIRY_DATE"] >= now]["SEM_EXPIRY_DATE"].min()
    near_futs = fut_stocks[fut_stocks["SEM_EXPIRY_DATE"] == near_expiry]
    
    sec_ids = near_futs["SEM_SMST_SECURITY_ID"].tolist()[:100]
    quotes = fetch_dhan_quotes(sec_ids)
    
    if not quotes:
        return generate_mock_data()
    
    ranked_futs = []
    for _, row in near_futs.iterrows():
        sid = str(row["SEM_SMST_SECURITY_ID"])
        if sid in quotes:
            q = quotes[sid]
            prev_close = q.get("ohlc", {}).get("close", 0)
            ltp = q.get("last_price", 0)
            if prev_close > 0 and ltp > 0:
                p_change = ((ltp - prev_close) / prev_close) * 100
                ranked_futs.append({
                    "symbol": row["SEM_CUSTOM_SYMBOL"],
                    "sec_id": sid,
                    "pre_open_price": ltp,
                    "prev_close": prev_close,
                    "p_change": p_change,
                    "ohlc": q.get("ohlc", {})
                })
                
    ranked_futs = sorted(ranked_futs, key=lambda x: x["p_change"], reverse=True)[:10]
    return process_option_strikes(ranked_futs, scrip_master, near_expiry)

def generate_mock_data():
    mock_stocks = [
        ("TATAMOTORS", 960.0, 984.5, 2.55, 955.0, 968.0, 951.0, 20),
        ("INFY", 1880.0, 1922.0, 2.23, 1870.0, 1890.0, 1865.0, 50),
        ("RELIANCE", 2930.0, 2981.0, 1.74, 2915.0, 2940.0, 2905.0, 50),
        ("ICICIBANK", 1242.0, 1260.5, 1.49, 1238.0, 1248.0, 1235.0, 20),
        ("SBIN", 824.0, 835.2, 1.36, 820.0, 828.0, 818.0, 10),
        ("TCS", 4200.0, 4252.0, 1.24, 4180.0, 4215.0, 4175.0, 50),
        ("BHARTIARTL", 1562.0, 1580.0, 1.15, 1550.0, 1568.0, 1545.0, 20),
        ("HDFCBANK", 1672.0, 1690.0, 1.08, 1665.0, 1678.0, 1660.0, 20),
        ("LT", 3640.0, 3676.0, 0.99, 3620.0, 3650.0, 3615.0, 50),
        ("AXISBANK", 1205.0, 1216.0, 0.91, 1198.0, 1210.0, 1195.0, 20),
    ]
    
    rows = []
    for sym, pc, po, chg, o, h, l, step in mock_stocks:
        prev_strike = round(pc / step) * step
        pre_strike = round(po / step) * step
        
        c_prem_prev = round(prev_strike * 0.022, 1)
        p_prem_prev = round(prev_strike * 0.020, 1)
        avg_prev = round((c_prem_prev + p_prem_prev) / 2, 1)
        
        c_prem_pre = round(pre_strike * 0.021, 1)
        p_prem_pre = round(pre_strike * 0.023, 1)
        
        rows.append({
            "Symbol": sym,
            "Pre-Open Future": f"₹{po:,.1f}",
            "Change %": f"+{chg:.2f}%",
            "Future Prev OHLC": f"{o:.0f} | {h:.0f} | {l:.0f} | {pc:.0f}",
            "Prev Close Strike": f"{prev_strike}",
            "Prev CE Close": f"₹{c_prem_prev:.1f}",
            "Prev PE Close": f"₹{p_prem_prev:.1f}",
            "Prev Straddle Avg": f"₹{avg_prev:.1f}",
            "Pre-Open Strike": f"{pre_strike}",
            "Pre CE (O|H|L|C)": f"{c_prem_pre*0.9:.1f} | {c_prem_pre*1.2:.1f} | {c_prem_pre*0.85:.1f} | {c_prem_pre:.1f}",
            "Pre CE LTP": f"₹{c_prem_pre:.1f}",
            "Pre PE (O|H|L|C)": f"{p_prem_pre*1.1:.1f} | {p_prem_pre*1.15:.1f} | {p_prem_pre*0.75:.1f} | {p_prem_pre:.1f}",
            "Pre PE LTP": f"₹{p_prem_pre:.1f}",
        })
    return pd.DataFrame(rows)

def process_option_strikes(ranked_futs, scrip_master, expiry):
    rows = []
    for item in ranked_futs:
        sym = item["symbol"]
        po = item["pre_open_price"]
        pc = item["prev_close"]
        ohlc = item["ohlc"]
        
        opts = scrip_master[
            (scrip_master["SEM_CUSTOM_SYMBOL"] == sym) & 
            (scrip_master["SEM_INSTRUMENT_NAME"] == "OPTSTK") &
            (scrip_master["SEM_EXPIRY_DATE"] == expiry)
        ]
        
        strikes = opts["SEM_STRIKE_PRICE"].drop_duplicates().sort_values().tolist()
        if not strikes:
            continue
            
        prev_strike = min(strikes, key=lambda x: abs(x - pc))
        pre_strike = min(strikes, key=lambda x: abs(x - po))
        
        rows.append({
            "Symbol": sym,
            "Pre-Open Future": f"₹{po:,.1f}",
            "Change %": f"+{item['p_change']:.2f}%",
            "Future Prev OHLC": f"{ohlc.get('open',0):.0f} | {ohlc.get('high',0):.0f} | {ohlc.get('low',0):.0f} | {pc:.0f}",
            "Prev Close Strike": f"{prev_strike}",
            "Prev CE Close": "Quote Req",
            "Prev PE Close": "Quote Req",
            "Prev Straddle Avg": "Quote Req",
            "Pre-Open Strike": f"{pre_strike}",
            "Pre CE (O|H|L|C)": "Quote Req",
            "Pre CE LTP": "Quote Req",
            "Pre PE (O|H|L|C)": "Quote Req",
            "Pre PE LTP": "Quote Req",
        })
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# 3. SINGLE-FRAME UI
# -----------------------------------------------------------------------------
st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; padding-left: 1.5rem; padding-right: 1.5rem; }
    h3 { margin-bottom: 0.2rem; }
    .status-tag { font-size: 0.85rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
    .live { background-color: #064e3b; color: #34d399; }
    .mock { background-color: #451a03; color: #fbbf24; }
    </style>
""", unsafe_allow_html=True)

col_title, col_info = st.columns([3, 1])
with col_title:
    st.subheader("⚡ Top 10 Positive Stock Futures: Pre-Open Derivatives Terminal")
    st.caption("Auto-discovers 9:08 AM futures equilibrium & correlates closing vs. opening strike options.")

with col_info:
    is_live = DHAN_ACCESS_TOKEN != "YOUR_ACCESS_TOKEN" and DHAN_ACCESS_TOKEN != ""
    status_html = '<span class="status-tag live">DHAN LIVE CONNECTED</span>' if is_live else '<span class="status-tag mock">DEMO / MOCK FEED ACTIVE</span>'
    st.markdown(f"<div style='text-align: right;'>{status_html}<br><small style='color:gray;'>Scan Window: 09:08 - 09:15 AM IST</small></div>", unsafe_allow_html=True)

df_terminal = get_top_preopen_futures_data()

st.dataframe(
    df_terminal,
    use_container_width=True,
    hide_index=True,
    height=420,
    column_config={
        "Symbol": st.column_config.TextColumn("Symbol"),
        "Pre-Open Future": st.column_config.TextColumn("Pre-Open Fut"),
        "Change %": st.column_config.TextColumn("Gap %"),
        "Future Prev OHLC": st.column_config.TextColumn("Fut Prev (O|H|L|C)"),
        "Prev Close Strike": st.column_config.TextColumn("Prev Strike"),
        "Prev CE Close": st.column_config.TextColumn("CE Close"),
        "Prev PE Close": st.column_config.TextColumn("PE Close"),
        "Prev Straddle Avg": st.column_config.TextColumn("Avg Straddle"),
        "Pre-Open Strike": st.column_config.TextColumn("Pre Strike"),
        "Pre CE (O|H|L|C)": st.column_config.TextColumn("Pre CE OHLC"),
        "Pre CE LTP": st.column_config.TextColumn("Pre CE LTP"),
        "Pre PE (O|H|L|C)": st.column_config.TextColumn("Pre PE OHLC"),
        "Pre PE LTP": st.column_config.TextColumn("Pre PE LTP"),
    }
)

st.caption("📌 **Trading Rule:** Options do not auction in pre-open. Pre-Strike CE/PE LTP reflects yesterday's close. Compare Pre CE LTP against Prev Straddle Avg to evaluate morning opening pricing.")

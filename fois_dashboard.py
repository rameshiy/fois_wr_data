import streamlit as st
import pandas as pd
import mysql.connector
import os
from datetime import datetime, timedelta
from mysql.connector import Error
import importlib
import sys

# Helper to get MySQL connection from environment variables
def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )

def get_table_names(connection):
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables

def get_max_tdate_and_count(connection, table_name):
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT MAX(TDATE), COUNT(*) FROM `{table_name}`")
        result = cursor.fetchone()
        return result[0], result[1] if result else (None, 0)
    except Exception:
        return None, 0
    finally:
        cursor.close()

def run_table_script(table_name):
    # Import and call run_for_table from fois_data_mysql.py
    try:
        if 'fois_data_mysql' in sys.modules:
            importlib.reload(sys.modules['fois_data_mysql'])
            fois_data_mysql = sys.modules['fois_data_mysql']
        else:
            fois_data_mysql = importlib.import_module('fois_data_mysql')
        # Accept both 'df_xxx' and 'xxx' as table_name
        key = table_name[3:] if table_name.startswith('df_') else table_name
        result = fois_data_mysql.run_for_table(key)
        if result:
            st.success(f"Script ran successfully for {table_name}")
        else:
            st.error(f"Script failed for {table_name}")
    except Exception as e:
        st.error(f"Error running script for {table_name}: {e}")

# --- Streamlit App ---
st.set_page_config(page_title="FOIS Data Dashboard", layout="wide", page_icon="📊")
st.markdown("""
    <style>
    body { background-color: #181c20; }
    .card {
        background: #e6f7e6;
        border-radius: 16px;
        box-shadow: 0 2px 8px #2222;
        padding: 1.5em 1em 1em 1em;
        margin-bottom: 1.5em;
        border: 2px solid #21ba45;
    }
    .card.red { background: #ffeaea; border-color: #db2828; }
    .card-header { font-size: 1.5em; font-weight: bold; color: #174c1b; margin-bottom: 0.2em; }
    .card-table { color: #444; font-size: 0.95em; margin-bottom: 0.7em; }
    .badge { display: inline-block; padding: 0.3em 0.9em; border-radius: 1em; font-weight: bold; font-size: 1em; margin-right: 0.5em; }
    .badge.green { background: #21ba45; color: #fff; }
    .badge.red { background: #db2828; color: #fff; }
    .badge.blue { background: #2185d0; color: #fff; }
    .run-btn { margin-top: 1em; }
    </style>
""", unsafe_allow_html=True)
st.title("FOIS Data Table Status Dashboard")

with st.spinner("Connecting to database..."):
    try:
        conn = get_mysql_connection()
        tables = get_table_names(conn)
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

df_tables = [t for t in tables if t.startswith('df_')]
# Responsive: 3 columns on wide screens, 1 on mobile
cols_per_row = 3 if len(df_tables) > 1 else 1
rows = [df_tables[i:i+cols_per_row] for i in range(0, len(df_tables), cols_per_row)]
yesterday = (datetime.now() - timedelta(days=1)).date()

for row in rows:
    cols = st.columns(len(row))
    for idx, table in enumerate(row):
        with cols[idx]:
            max_tdate, row_count = get_max_tdate_and_count(conn, table)
            is_green = max_tdate and str(max_tdate) == str(yesterday)
            card_color = "" if is_green else " red"
            # Start card div
            card_html = f"""
            <div class='card{card_color}'>
                <div class='card-header'>USFD Work Load</div>
                <div class='card-table'>(<b>{table}</b>)</div>
                <span class='badge {'green' if is_green else 'red'}'>TDATE: {str(max_tdate) if max_tdate else 'N/A'}</span>
                <span class='badge blue'>Rows: {row_count}</span>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"Run Script for {table.upper()}", key=f"run_{table}"):
                run_table_script(table)

if conn:
    conn.close()

import requests
import json
import os
import base64
import argparse
import sys
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import APIError, WorksheetNotFound

# ---------------------- FOIS API Client ----------------------
class FOISAPIClient:
    """
    Handles authentication and requests to the Indian Railway FOIS API.
    """
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        if not self.client_id or not self.client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in .env file")
        self.token_url = "https://gw.crisapis.indianrail.gov.in/token"
        self.revoke_url = "https://gw.crisapis.indianrail.gov.in/revoke"
        self.access_token = None
        self.token_expires_at = None

    def get_access_token(self):
        """
        Obtain a new access token using client credentials.
        """
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}
        try:
            print("Requesting access token...")
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            print(f"✓ Access token obtained successfully (expires in {expires_in} seconds)")
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"Error getting access token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response: {e.response.text}")
            raise

    def is_token_valid(self):
        """
        Check if the current token is valid and not expired.
        """
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at

    def ensure_valid_token(self):
        """
        Ensure a valid access token is available.
        """
        if not self.is_token_valid():
            self.get_access_token()
        return self.access_token

    def revoke_token(self):
        """
        Revoke the current access token.
        """
        if not self.access_token:
            print("No token to revoke")
            return
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"token": self.access_token}
        try:
            print("Revoking access token...")
            response = requests.post(self.revoke_url, headers=headers, data=data)
            response.raise_for_status()
            self.access_token = None
            self.token_expires_at = None
            print("✓ Token revoked successfully")
        except requests.exceptions.RequestException as e:
            print(f"Error revoking token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response: {e.response.text}")

# ---------------------- Google Sheets Helpers ----------------------
def get_gspread_client():
    """
    Authenticate and return a gspread client using service account credentials.
    """
    scope = [
        "https://spreadsheets.google.com/feeds",
        'https://www.googleapis.com/auth/spreadsheets',
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
    return gspread.authorize(creds)

def get_spreadsheet(gclient):
    """
    Open the Google Spreadsheet using ID from environment variable.
    """
    spreadsheet_id = os.getenv("GSHEET_ID")
    spreadsheet_name = os.getenv("GSHEET_NAME")
    if not spreadsheet_id:
        print("❌ GSHEET_ID not set in .env file.")
        sys.exit(1)
    spreadsheet = gclient.open_by_key(spreadsheet_id)
    print(f"Connected to Google Sheet: {spreadsheet_name or spreadsheet.title}")
    return spreadsheet

def push_df_to_gsheet(df, df_var_name, spreadsheet, retries=3, delay=5):
    """
    Push a DataFrame to a Google Sheet tab named as df_var_name with retries.
    If the sheet does not exist, create it. If it exists, append data.
    """
    df = df.astype(str)
    headers = df.columns.tolist()
    rows = df.values.tolist()
    for attempt in range(retries):
        try:
            worksheet = spreadsheet.worksheet(df_var_name)
            existing_rows = len(worksheet.get_all_values())
            if existing_rows == 0:
                worksheet.append_row(headers)
            if rows:
                worksheet.append_rows(rows)
            print(f"✅ Data from {df_var_name} written to Google Sheets.")
            return
        except WorksheetNotFound:
            try:
                worksheet = spreadsheet.add_worksheet(title=df_var_name, rows=str(len(rows)+10), cols=str(len(headers)+5))
                worksheet.append_row(headers)
                if rows:
                    worksheet.append_rows(rows)
                print(f"✅ Data from {df_var_name} written to Google Sheets.")
                return
            except APIError as e:
                if '500' in str(e):
                    print(f"⚠ Attempt {attempt + 1}/{retries} failed: Google Sheets APIError [500]. Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    raise
        except APIError as e:
            if '500' in str(e):
                print(f"⚠ Attempt {attempt + 1}/{retries} failed: Google Sheets APIError [500]. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise
    print(f"❌ Failed to write {df_var_name} to Google Sheets after {retries} attempts.")

def sheet_has_today(spreadsheet, df_var_name, today_str):
    """
    Check if the worksheet for df_var_name has TDATE == today_str in any row.
    Returns True if today's date is found, False otherwise.
    """
    try:
        worksheet = spreadsheet.worksheet(df_var_name)
        all_values = worksheet.get_all_values()
        if not all_values or "TDATE" not in all_values[0]:
            return False
        tdate_idx = all_values[0].index("TDATE")
        for row in all_values[1:]:
            if len(row) > tdate_idx and row[tdate_idx] == today_str:
                return True
        return False
    except WorksheetNotFound:
        return False

# ---------------------- Data Fetching Logic ----------------------
def fetch_fois_data(client, config, spreadsheet):
    """
    Fetch data from Indian Railway FOIS API, apply zone filter, and push to Google Sheets.
    Only fetch and append if today's date is not already present in the sheet.
    """
    df_var_name = f"df_{config['table_name']}"
    date_str = (datetime.now() - timedelta(days=config['date_config']['deltadays'])).strftime(config['date_config']['formatter'])
    print(f"Using date {date_str} for {df_var_name} API call")
    # Skip if today's data already present in Google Sheet
    if sheet_has_today(spreadsheet, df_var_name, date_str):
        print(f"⏩ Skipping {df_var_name}: TDATE {date_str} already present.")
        return None
    try:
        token = client.ensure_valid_token()
        params = {"date": date_str}
        headers = config['headers'].copy()
        headers["Authorization"] = headers["Authorization"].replace("@token", token)
        response = requests.get(config['url'], params=params, headers=headers)
        response.raise_for_status()
        try:
            data = response.json()
            if isinstance(data, list) and data and isinstance(data[0], dict):
                df = pd.DataFrame(data)
                # Apply appropriate zone filter based on endpoint
                zone_column = 'dstnzone' if config['table_name'] == 'fois_od_data' else 'zone'
                if zone_column in df.columns:
                    if config['table_name'] == 'fois_od_data':
                        # For fois_od_data, filter where dstnzone == 'WR' or srczone == 'WR'
                        df = df[(df['dstnzone'] == 'WR') | (df['srczone'] == 'WR')]
                    else:
                        df = df[df[zone_column] == 'WR']
                    if df.empty:
                        print(f"\n{df_var_name} =")
                        print(f"No data found for {zone_column}='WR'")
                        return data
                df.insert(0, "TDATE", date_str)
                globals()[df_var_name] = df
                print(f"\n{df_var_name} =")
                print(df)
                push_df_to_gsheet(df, df_var_name, spreadsheet)
            return data
        except json.JSONDecodeError:
            print("Response is not valid JSON. Raw response:")
            print(response.text)
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error making request for {df_var_name}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
            if e.response.status_code == 401:
                client.access_token = None
                client.token_expires_at = None
                try:
                    token = client.ensure_valid_token()
                    headers["Authorization"] = f"Bearer {token}"
                    response = requests.get(config['url'], params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        df = pd.DataFrame(data)
                        # Apply appropriate zone filter based on endpoint
                        zone_column = 'dstnzone' if config['table_name'] == 'fois_od_data' else 'zone'
                        if zone_column in df.columns:
                            if config['table_name'] == 'fois_od_data':
                                df = df[(df['dstnzone'] == 'WR') | (df['srczone'] == 'WR')]
                            else:
                                df = df[df[zone_column] == 'WR']
                            if df.empty:
                                print(f"\n{df_var_name} =")
                                print(f"No data found for {zone_column}='WR'")
                                return data
                        df.insert(0, "TDATE", date_str)
                        globals()[df_var_name] = df
                        print(f"\n{df_var_name} =")
                        print(df)
                        push_df_to_gsheet(df, df_var_name, spreadsheet)
                    return data
                except Exception as retry_error:
                    print(f"Retry failed for {df_var_name}: {retry_error}")
        return None

# ---------------------- Utility Functions ----------------------
def get_api_configs():
    """
    Return list of API configurations for FOIS endpoints.
    """
    return [
        {
            "url": "https://gw.crisapis.indianrail.gov.in/t/fois.cris.in/foisrlydashb/1.0/pndgindt",
            "method": "GET",
            "date_config": {"formatter": "%d-%m-%Y", "deltadays": 1},
            "headers": {"accept": "*/*", "Authorization": "Bearer @token"},
            "parameters": {"date": "@toDate"},
            "table_name": "fois_indent_data"
        },
        {
            "url": "https://gw.crisapis.indianrail.gov.in/t/fois.cris.in/foisrlydashb/1.0/plctresndttn",
            "method": "GET",
            "date_config": {"formatter": "%d-%m-%Y", "deltadays": 1},
            "headers": {"accept": "*/*", "Authorization": "Bearer @token"},
            "parameters": {"date": "@toDate"},
            "table_name": "fois_detn_data"
        },
        {
            "url": "https://gw.crisapis.indianrail.gov.in/t/fois.cris.in/foisrlydashb/1.0/wghtleadntkmfrgt",
            "method": "GET",
            "date_config": {"formatter": "%d-%m-%Y", "deltadays": 1},  # Changed to fetch yesterday's data
            "headers": {"accept": "*/*", "Authorization": "Bearer @token"},
            "parameters": {"date": "@fromDate"},
            "table_name": "fois_od_data"
        }
    ]

def parse_arguments():
    """
    Parse command line arguments to select specific API endpoint.
    """
    parser = argparse.ArgumentParser(description='Indian Railway FOIS API Data Fetcher')
    parser.add_argument('--endpoint', 
                        help='Endpoint to fetch data for (pndgindt, plctresndttn, wghtleadntkmfrgt) or index (1-3)',
                        required=False)
    return parser.parse_args()

# ---------------------- Main Execution ----------------------
def main():
    """
    Main function to execute the FOIS API calls and push data to Google Sheets.
    """
    try:
        args = parse_arguments()
        client = FOISAPIClient()
        api_configs = get_api_configs()

        # Determine which endpoints to run
        if args.endpoint:
            endpoint_arg = args.endpoint.strip()
            if endpoint_arg.isdigit():
                idx = int(endpoint_arg)
                if 1 <= idx <= len(api_configs):
                    api_configs_to_run = [api_configs[idx - 1]]
                else:
                    print(f"Error: Endpoint index {idx} is out of range (1-{len(api_configs)})")
                    sys.exit(1)
            else:
                api_configs_to_run = [config for config in api_configs if config['url'].endswith(endpoint_arg)]
                if not api_configs_to_run:
                    print(f"Error: Endpoint '{endpoint_arg}' is not valid.")
                    sys.exit(1)
        else:
            api_configs_to_run = api_configs

        # Setup Google Sheets connection
        gclient = get_gspread_client()
        spreadsheet = get_spreadsheet(gclient)

        # Fetch and push data for each endpoint
        for config in api_configs_to_run:
            endpoint_name = config['url'].split('/')[-1]
            print(f"\nFetching data for endpoint: {endpoint_name}")
            date_str = (datetime.now() - timedelta(days=config['date_config']['deltadays'])).strftime(config['date_config']['formatter'])
            print(f"Date: {date_str}")
            success = fetch_fois_data(client, config, spreadsheet)
            if success is None:
                print(f"Failed to fetch data for {endpoint_name}")
            time.sleep(1)  # Delay to avoid hitting Google Sheets API rate limits

        client.revoke_token()
        sys.exit(0)
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease ensure your .env file contains:")
        print("CLIENT_ID=your_client_id_here")
        print("CLIENT_SECRET=your_client_secret_here")
        print("GSHEET_ID=your_spreadsheet_id_here")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease ensure 'gs_credentials.json' is present in the working directory.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
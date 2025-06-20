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
import mysql.connector
from mysql.connector import Error

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

# ---------------------- MySQL Helpers ----------------------
def get_mysql_connection():
    """
    Create and return a MySQL database connection using credentials from .env.
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE')
        )
        if connection.is_connected():
            print(f"Connected to MySQL database: {os.getenv('MYSQL_DATABASE')}")
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

def table_exists(connection, table_name):
    """
    Check if a table exists in the database.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        result = cursor.fetchone()
        print(f"Table {table_name} exists: {result is not None}")
        return result is not None
    except Error as e:
        print(f"Error checking table existence for {table_name}: {e}")
        return False
    finally:
        if cursor is not None:
            cursor.close()

def infer_mysql_type(dtype, column_name):
    """
    Map pandas dtype to MySQL data type, with special handling for TDATE.
    """
    if column_name == 'TDATE':
        return 'DATE'
    dtype = str(dtype).lower()
    if 'int' in dtype:
        return 'BIGINT'
    elif 'float' in dtype:
        return 'DOUBLE'
    elif 'datetime' in dtype:
        return 'DATETIME'
    elif 'bool' in dtype:
        return 'BOOLEAN'
    else:
        return 'TEXT'

def create_table_if_not_exists(connection, table_name, df):
    """
    Create a table if it doesn't exist, using DataFrame columns and inferred types.
    """
    try:
        cursor = connection.cursor()
        columns = df.columns.tolist()
        mysql_types = []
        for col in columns:
            mysql_type = infer_mysql_type(df[col].dtype, col)
            mysql_types.append(f"`{col}` {mysql_type}")
        columns_sql = ", ".join(mysql_types)
        # Add an auto-incrementing ID as primary key to avoid issues with composite keys
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            {columns_sql}
        )
        """
        print(f"Executing table creation SQL for {table_name}:\n{create_table_sql}")
        cursor.execute(create_table_sql)
        connection.commit()
        print(f"Table {table_name} checked/created successfully.")
        cursor.close()
    except Error as e:
        print(f"Error creating table {table_name}: {e}")
        raise

def data_exists_for_date(connection, table_name, date_str):
    """
    Check if data for the given date exists in the table.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        # Convert date_str to YYYY-MM-DD for MySQL query
        api_date = datetime.strptime(date_str, '%d-%m-%Y').strftime('%Y-%m-%d')
        query = f"SELECT COUNT(*) FROM `{table_name}` WHERE TDATE = %s"
        cursor.execute(query, (api_date,))
        count = cursor.fetchone()[0]
        print(f"Data for {api_date} in {table_name}: {'exists' if count > 0 else 'does not exist'}")
        return count > 0
    except Error as e:
        print(f"Error checking existing data in {table_name}: {e}")
        return False
    finally:
        if cursor is not None:
            cursor.close()

def insert_data_to_mysql(df, table_name, connection, retries=3, delay=5):
    """
    Insert DataFrame data into the MySQL table with retries.
    """
    # Convert TDATE to YYYY-MM-DD format for MySQL DATE type
    if 'TDATE' in df.columns:
        df['TDATE'] = pd.to_datetime(df['TDATE'], format='%d-%m-%Y').dt.strftime('%Y-%m-%d')
        df['TDATE'] = pd.to_datetime(df['TDATE'], format='%Y-%m-%d').dt.date
    # Convert all other columns to string for consistency, except TDATE
    for col in df.columns:
        if col != 'TDATE':
            df[col] = df[col].astype(str)
    columns = df.columns.tolist()
    placeholders = ', '.join(['%s'] * len(columns))
    columns_sql = ', '.join([f"`{col}`" for col in columns])
    insert_sql = f"INSERT INTO `{table_name}` ({columns_sql}) VALUES ({placeholders})"
    
    for attempt in range(retries):
        cursor = None
        try:
            cursor = connection.cursor()
            # Ensure table exists before inserting
            if not table_exists(connection, table_name):
                print(f"Table {table_name} does not exist, creating it...")
                create_table_if_not_exists(connection, table_name, df)
            else:
                print(f"Table {table_name} already exists, proceeding with insert.")
            for _, row in df.iterrows():
                cursor.execute(insert_sql, tuple(row))
            connection.commit()
            print(f"✅ Data from {table_name} inserted into MySQL ({len(df)} rows).")
            # Only close cursor here after successful insert
            if cursor is not None:
                cursor.close()
            return
        except Error as e:
            print(f"⚠ Attempt {attempt + 1}/{retries} failed: MySQL Error: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
            if attempt == retries - 1:
                print(f"❌ Failed to insert data into {table_name} after {retries} attempts.")
                raise
        finally:
            # Only close cursor if it exists and is not already closed, and only if exception occurred
            if cursor is not None:
                try:
                    cursor.close()
                except:
                    pass

# ---------------------- Data Fetching Logic ----------------------
def fetch_fois_data(client, config, connection):
    """
    Fetch data from Indian Railway FOIS API, apply zone filter, and store in MySQL.
    Only fetch and insert if today's date is not already present in the table.
    """
    table_name = f"df_{config['table_name']}"
    date_str = (datetime.now() - timedelta(days=config['date_config']['deltadays'])).strftime(config['date_config']['formatter'])
    print(f"Using date {date_str} for {table_name} API call")
    # Skip if today's data already present in MySQL table
    if data_exists_for_date(connection, table_name, date_str):
        print(f"⏩ Skipping {table_name}: TDATE {date_str} already present.")
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
                        df = df[(df['dstnzone'] == 'WR') | (df['srczone'] == 'WR')]
                    else:
                        df = df[df[zone_column] == 'WR']
                    if df.empty:
                        print(f"\n{table_name} =")
                        print(f"No data found for {zone_column}='WR'")
                        return data
                df.insert(0, "TDATE", date_str)
                globals()[table_name] = df
                print(f"\n{table_name} =")
                print(df)
                insert_data_to_mysql(df, table_name, connection)
            return data
        except json.JSONDecodeError:
            print("Response is not valid JSON. Raw response:")
            print(response.text)
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error making request for {table_name}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
            if e.response.status_code == 401:
                client.access_token = None
                client.token_expires_at = None
                try:
                    # Ensure params and headers are defined in this scope
                    token = client.ensure_valid_token()
                    params = {"date": date_str}
                    headers = config['headers'].copy()
                    headers["Authorization"] = f"Bearer {token}"
                    response = requests.get(config['url'], params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        df = pd.DataFrame(data)
                        zone_column = 'dstnzone' if config['table_name'] == 'fois_od_data' else 'zone'
                        if zone_column in df.columns:
                            if config['table_name'] == 'fois_od_data':
                                df = df[(df['dstnzone'] == 'WR') | (df['srczone'] == 'WR')]
                            else:
                                df = df[df[zone_column] == 'WR']
                            if df.empty:
                                print(f"\n{table_name} =")
                                print(f"No data found for {zone_column}='WR'")
                                return data
                        df.insert(0, "TDATE", date_str)
                        globals()[table_name] = df
                        print(f"\n{table_name} =")
                        print(df)
                        insert_data_to_mysql(df, table_name, connection)
                    return data
                except Exception as retry_error:
                    print(f"Retry failed for {table_name}: {retry_error}")
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
            "date_config": {"formatter": "%d-%m-%Y", "deltadays": 1},
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
    Main function to execute the FOIS API calls and store data in MySQL.
    """
    connection = None  # Ensure connection is defined for finally block
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
                # Match by endpoint name (last part of URL or table_name)
                api_configs_to_run = [
                    config for config in api_configs
                    if config['url'].split('/')[-1] == endpoint_arg or config['table_name'] == endpoint_arg
                ]
                if not api_configs_to_run:
                    print(f"Error: Endpoint '{endpoint_arg}' is not valid.")
                    sys.exit(1)
        else:
            api_configs_to_run = api_configs

        # Setup MySQL connection
        connection = get_mysql_connection()

        # Fetch and store data for each endpoint
        for config in api_configs_to_run:
            endpoint_name = config['url'].split('/')[-1]
            print(f"\nFetching data for endpoint: {endpoint_name}")
            date_str = (datetime.now() - timedelta(days=config['date_config']['deltadays'])).strftime(config['date_config']['formatter'])
            print(f"Date: {date_str}")
            try:
                success = fetch_fois_data(client, config, connection)
                if success is None:
                    print(f"Failed to fetch data for {endpoint_name}")
            except Exception as e:
                print(f"Exception while fetching data for {endpoint_name}: {e}")
            time.sleep(1)  # Delay to avoid rate limits

        client.revoke_token()
        if connection is not None and hasattr(connection, "is_connected") and connection.is_connected():
            connection.close()
            print("MySQL connection closed.")
        sys.exit(0)
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nPlease ensure your .env file contains:")
        print("CLIENT_ID=your_client_id_here")
        print("CLIENT_SECRET=your_client_secret_here")
        print("MYSQL_HOST=your_mysql_host")
        print("MYSQL_USER=your_mysql_user")
        print("MYSQL_PASSWORD=your_mysql_password")
        print("MYSQL_DATABASE=your_mysql_database")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if connection is not None and hasattr(connection, "is_connected") and connection.is_connected():
            connection.close()
            print("MySQL connection closed.")

def run_for_table(table_key):
    """
    Run the FOIS data fetch for a specific table (by table_name or index).
    Returns True if successful, False otherwise.
    """
    connection = None
    try:
        client = FOISAPIClient()
        api_configs = get_api_configs()
        # Accept either table_name (e.g., 'fois_detn_data') or index (1-based)
        if isinstance(table_key, int) or (isinstance(table_key, str) and table_key.isdigit()):
            idx = int(table_key)
            if 1 <= idx <= len(api_configs):
                configs_to_run = [api_configs[idx - 1]]
            else:
                print(f"Index {idx} out of range.")
                return False
        else:
            configs_to_run = [cfg for cfg in api_configs if cfg['table_name'] == table_key or f"df_{cfg['table_name']}" == table_key]
            if not configs_to_run:
                print(f"No config found for {table_key}")
                return False
        connection = get_mysql_connection()
        for config in configs_to_run:
            print(f"Running fetch for {config['table_name']}")
            fetch_fois_data(client, config, connection)
        client.revoke_token()
        if connection and hasattr(connection, 'is_connected') and connection.is_connected():
            connection.close()
        return True
    except Exception as e:
        print(f"Error running for table {table_key}: {e}")
        if connection and hasattr(connection, 'is_connected') and connection.is_connected():
            connection.close()
        return False

if __name__ == "__main__":
    main()
FOIS API Client 🚂
A Python client for accessing Freight Operations Information System (FOIS) data through the Indian Railway CRIS (Centre for Railway Information Systems) API. This tool fetches historic railway freight data, filters it for Western Railway, and stores it in Google Sheets.
📋 Description
This application interacts with the FOIS API to retrieve freight-related data, including indent data, detention data, and weight/lead statistics. It supports fetching data for multiple days, applies zone filters (zone = "WR" or dstnzone = "WR" or srczone = "WR"), and pushes results to Google Sheets. The client handles OAuth2 authentication and includes rate limit mitigation for reliable operation.
✨ Features

🔐 Dynamic OAuth2 Authentication - Automatic token generation and management
📊 Multiple Endpoints - Access three FOIS data categories: pndgindt, plctresndttn, wghtleadntkmfrgt
🔄 Historic Data Fetching - Fetch data for a user-specified number of days
🎯 Zone Filtering - Filters data for Western Railway (WR) zones
🛡️ Rate Limit Handling - 60-second pause after 10 API calls to avoid errors
📁 Google Sheets Integration - Stores data in separate tabs with duplicate date checking
🧹 Clean Exit - Proper token revocation on application exit
📝 Environment Variables - Secure credential management via .env file

Available Data Endpoints



Endpoint
Description
Filter Applied



pndgindt
Pending Indent Data
zone = "WR"


plctresndttn
Placement and Release Detention Data
zone = "WR"


wghtleadntkmfrgt
Weight, Lead, NTKM, and Freight Data
dstnzone = "WR" or srczone = "WR"


🔧 Requirements

Python: 3.7+
Dependencies: Listed in requirements.txt

Python Packages
requests
python-dotenv
pandas
gspread
oauth2client

🚀 Installation

Install dependencies
pip install -r requirements.txt


Create environment file
Create a .env file in the project root with your API and Google Sheets credentials:
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
GSHEET_ID=your_spreadsheet_id_here
GSHEET_NAME=your_spreadsheet_name_here


Note: Obtain FOIS API credentials from the Indian Railway CRIS portal. Google Sheets credentials require a service account.


Set up Google Sheets service account

Create a service account in Google Cloud Console.
Download the service account key as gs_credentials.json and place it in the project root.
Share the target spreadsheet (GSHEET_ID) with the service account email (from gs_credentials.json) with "Editor" permissions.



🎮 Usage
Running the Script
python fois_data_historic.py --days <number_of_days> [--endpoint <endpoint_name_or_index>]

Command-Line Arguments

--days <number>: Required. Number of days to fetch data for, starting from yesterday (e.g., 5 for past 5 days).
--endpoint <name_or_index>: Optional. Specify a single endpoint (pndgindt, plctresndttn, wghtleadntkmfrgt) or index (1, 2, 3). Omit to run all endpoints.

Examples

Fetch data for 5 days, all endpoints:python fois_data_historic.py --days 5


Fetch data for 3 days, only plctresndttn:python fois_data_historic.py --days 3 --endpoint plctresndttn


Fetch data for 10 days, wghtleadntkmfrgt (index 3):python fois_data_historic.py --days 10 --endpoint 3



📊 Example Output
For --days 2 --endpoint pndgindt:
Connected to Google Sheet: FOIS Data
Processing endpoint: pndgindt for date 05-06-2025
Fetching data for df_fois_indent_data with date 05-06-2025
df_fois_indent_data =
   TDATE      ar_dp  ...  zone
0  05-06-2025  123   ...  WR
1  05-06-2025  456   ...  WR
...
✅ Data from df_fois_indent_data written to Google Sheets.
Processing endpoint: pndgindt for date 04-06-2025
Fetching data for df_fois_indent_data with date 04-06-2025
...
Completed processing. Total API calls made: 2

For wghtleadntkmfrgt:
Fetching data for df_fois_od_data with date 05-06-2025
df_fois_od_data =
   TDATE  cmdt  dstnzone  srczone  ...
0  05-06-2025  COAL  WR       NR      ...
1  05-06-2025  IRON  NR       WR      ...
...
✅ Data from df_fois_od_data written to Google Sheets.

📁 File Structure
fois-api-client/
├── fois_data_historic.py   # Main application script
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── .env                    # Environment variables (create this)
├── gs_credentials.json     # Google Sheets service account key (create this)
└── .gitignore              # Git ignore file

⚠️ Confidentiality Notice
Important: This project involves API keys and Google Sheets credentials. Sharing or exposing these publicly is strictly prohibited and may violate terms of service or data protection regulations (e.g., Data Protection Act). The script owner/user is solely responsible for securely storing all credentials and ensuring they are not included in public repositories or shared documentation.
🚨 NOTE
The script will:✓ Check for existing data by date to avoid duplicates✓ Pause for 60 seconds after 10 API calls to prevent rate limit errors✓ Retry Google Sheets API calls (3 attempts) for server errors✓ Log the endpoint and date for each API call✓ Require a valid --days argument (positive integer)
🔑 Environment Variables
Create a .env file with the following variables:



Variable
Description
Required



CLIENT_ID
FOIS API client ID
✅ Yes


CLIENT_SECRET
FOIS API client secret
✅ Yes


GSHEET_ID
Google Spreadsheet ID
✅ Yes


GSHEET_NAME
Google Spreadsheet name
Optional


🚨 Error Handling
The application includes comprehensive error handling for:

Authentication failures - Invalid API credentials or expired tokens
Network issues - Connection timeouts or server errors
API errors - Rate limits


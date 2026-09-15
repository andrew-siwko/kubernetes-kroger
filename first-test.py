
def load_variable(variable_name,cl_position=None):
    result=None
    if cl_position:
        import sys
        if len(sys.argv)>cl_position:
            result=sys.argv[cl_position]
    if result==None:
        import os
        result=os.getenv(variable_name)
        if result is None:
            try:
                import winreg
                result=winreg.QueryValue(winreg.CreateKey(winreg.HKEY_CURRENT_USER,None),variable_name)
            except FileNotFoundError:
                print('variable definition missing:',variable_name)
                print('add to environment or registry under HKEY_CURRENT_USER')
                exit()
            except ModuleNotFoundError:
                print('Registry module not available')
                exit()
    return result


import requests

token_url = "https://api.kroger.com/v1/connect/oauth2/token"

client_id = load_variable('KROGER_CLIENT_ID',1)
client_secret = load_variable('KROGER_CLIENT_SECRET',2)

# Option 1: Client Credentials Grant (General data / app-level access)
payload = {
    "grant_type": "client_credentials",
    "scope": "product.compact",  # adjust scope as needed
}

# The requests library 'auth' tuple automatically handles Base64 encoding 
# of client_id:client_secret and sets the 'Authorization: Basic ...' header.
response = requests.post(token_url,data=payload,headers={"Content-Type": "application/x-www-form-urlencoded"},auth=(client_id, client_secret))

# Raise an exception for HTTP error codes
response.raise_for_status()

token_data = response.json()
access_token = token_data["access_token"]
# print("Access Token:", access_token)


url = "https://api.kroger.com/v1/products"
params = {
    "filter.term": "milk",
    "filter.limit": 2,
}
headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}",  # Replace with your actual token string
}

response = requests.get(url, params=params, headers=headers)
response.raise_for_status()

data = response.json()
import pprint
pprint.pprint(data)
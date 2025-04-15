# hubspot.py
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import json,secrets,httpx,asyncio,base64,requests,time
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

REDIRECT_URI = "http://localhost:8000/integrations/hubspot/oauth2callback"
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_seceret"
AUTHORIZATION_URI = f"https://app-na2.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=oauth%20crm.objects.companies.read%20crm.objects.contacts.read"

encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

async def authorize_hubspot(user_id, org_id):
    """
    Generates a HubSpot OAuth2 authorization URL with a secure state parameter.
    
    Args:
        user_id: Unique identifier for the user initiating the OAuth flow.
        org_id: Unique identifier for the organization associated with the user.
    
    Returns:
        str: The HubSpot authorization URL with embedded state data.
    """
    # secure state
    state_payload = {
        'csrf_token': secrets.token_urlsafe(32),  
        'user_id': user_id,
        'org_id': org_id,
    }

    # Encode state securely
    encoded_state = base64.urlsafe_b64encode( json.dumps(state_payload).encode('utf-8')).decode('utf-8')

    # Construct authorization URL
    auth_url = f"{AUTHORIZATION_URI}&state={encoded_state}"

    # Store state securely in Redis with TTL
    redis_key_hubspot = f"hubspot_auth:{org_id}:{user_id}"
    await add_key_value_redis(redis_key_hubspot, encoded_state, expire=600)

    return auth_url 

async def oauth2callback_hubspot(request: Request):
    """
    Handle OAuth2 callback, verify state, and exchange code for access token.
    
    Args:
        request (Request): FastAPI request object with query params
    
    Returns:
        dict: Access token and success message, or error
    """
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    
    # Extract query parameters
    query_params = request.query_params

    auth_code = query_params.get("code")
    encoded_state = query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    
    # Verify state from Redis
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')
    redis_key_hubspot = f"hubspot_auth:{org_id}:{user_id}"
    cached_state = await get_value_redis(redis_key_hubspot)

    if not auth_code or not state_data:
        raise HTTPException(status_code=400, detail='State does not match.')
    
    if not cached_state:
        raise HTTPException(status_code=400, detail='Invalid or expired state')

    await delete_key_redis(redis_key_hubspot)  # Clean up state
    
    # Exchange code for access token
    token_url = "https://api.hubapi.com/oauth/v1/token"
    
    async with httpx.AsyncClient() as client:
        payload = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code
        }
        response = await client.post(token_url, data=payload)

    # if response.status_code == 200:
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=1800)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)    

async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieve cached HubSpot access token from Redis.
    
    Args:
        user_id (str): User ID from the form
        org_id (str): Organization ID from the form
    
    Returns:
        dict: Access token or error
    """
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
        
    
    credentials = json.loads(credentials)

    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

async def create_integration_item_metadata_object(response_json: dict, item_type: str) -> IntegrationItem:
    """
    Transforms a HubSpot contact or company object into a standard IntegrationItem.
    
    Args:
        response_json (dict): The HubSpot response item (a contact or a company).
        item_type (str): Either 'contact' or 'company'.

    Returns:
        IntegrationItem: Normalized object.
    """
    properties = response_json.get("properties", {})

    if item_type == "contact":
        first = properties.get("firstname", "")
        last = properties.get("lastname", "")
        temp_email = properties.get("email","")
        name = f"{first} {last}".strip() or f"Contact {response_json['id']}"
    elif item_type == "company":
        temp_email = properties.get("domain","")
        name = properties.get("name", f"Company {response_json['id']}")
    else:
        name = f"{item_type.capitalize()} {response_json['id']}"

    # Dates
    creation_time = properties.get("createdate") or response_json.get("createdAt")
    last_modified_time = properties.get("lastmodifieddate") or response_json.get("updatedAt")

    return IntegrationItem(
        id=response_json.get("id"),
        type=item_type,
        name=name,
        creation_time=creation_time,
        last_modified_time=last_modified_time,
        directory="False",
        url=temp_email,
        visibility= str( response_json.get("archived", "False")),
    )

async def get_items_hubspot(credentials: str, user:str, org:str):
    """
    Fetch all contacts and companies from HubSpot CRM using the access token.
    
    Args:
        credentials (str): Access token from the form
    
    Returns:
        dict: Contacts and companies data
    """
    credentials = json.loads(credentials)
    headers = {
        "Authorization": f"Bearer {credentials.get('access_token')}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Fetch contacts
        contacts_url = "https://api.hubapi.com/crm/v3/objects/contacts"
        all_contacts = []
        after = None
        
        while True:
            params = {"limit": 100}
            if after:
                params["after"] = after

            response = await client.get(contacts_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                all_contacts.extend(data["results"])
                if "paging" in data and "next" in data["paging"]:
                    after = data["paging"]["next"]["after"]
                else:
                    break
            else:
                return {"error": f"Failed to fetch contacts: {response.text}"}
        
        # Fetch companies
        companies_url = "https://api.hubapi.com/crm/v3/objects/companies"
        all_companies = []
        after = None
        
        while True:
            params = {"limit": 100}
            if after:
                params["after"] = after
            response = await client.get(companies_url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                all_companies.extend(data["results"])
                if "paging" in data and "next" in data["paging"]:
                    after = data["paging"]["next"]["after"]
                else:
                    break
            else:
                return {"error": f"Failed to fetch companies: {response.text}"}
            
    #  Convert to IntegrationItem objects
    integration_contacts = [
        await create_integration_item_metadata_object(contact, "contact")
        for contact in all_contacts
    ]

    integration_companies = [
        await create_integration_item_metadata_object(company, "company")
        for company in all_companies
    ]
    return_data = integration_companies +integration_contacts
    await add_key_value_redis(f'hubspot_data:{org}:{user}', json.dumps([item.__dict__ for item in return_data]))
    
    return return_data

async def transfer_hubspot_items(to_org,user,org,target_credentials):
    try:
        some_data = await get_value_redis(f'hubspot_data:{org}:{user}')
        ts_data = json.loads(some_data)
        stf_credentials = json.loads(target_credentials)
        if to_org == "notion":
            response  = await create_notion_page_from_data(credentials=stf_credentials,data=ts_data)

        elif to_org == "airtable":
            response  = await create_airtable_fromdata(credentials=stf_credentials,data=ts_data)

        return response.json()
    except Exception as e:
        print(" ERROR in transfer",e)

async def create_notion_page_from_data(credentials: dict, data: dict, title: str = "Imported Data"):
    """
    Creates a new Notion page with your provided data in a structured format.

    Args:
        credentials (dict): Notion access token and other details
        data (dict): The content you want to insert (e.g., contact, company)
        title (str): Title of the Notion page

    Returns:
        dict: Notion response
    """
    access_token = credentials.get("access_token")
    if not access_token:
        return {"error": "Missing Notion access token"}

    page_id = "1a86e6bfdf9e4f6482e571ba6aa34a89"

    formatted_text = json.dumps(data, indent=2)

    max_length = 2000
    chunks = [formatted_text[i:i + max_length] for i in range(0, len(formatted_text), max_length)]

    # Create payload with multiple paragraph blocks
    payload = {
        "children": [   
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": chunk
                            }
                        }
                    ]}}for chunk in chunks] }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers, json=payload)

    if response.status_code == 200:
        return response
    else:
        return {
            "error": f"Failed to create Notion page",
            "status_code": response.status_code,
            "response": response.text
        }

async def create_airtable_fromdata(credentials:str, data:dict):
    
    base_id = "app1jyhL3DTV7lGwk"
    table_id= "tblNLBhL0YkldMTB7"
    access_token = credentials.get("access_token")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    max_records_per_request = 10

    async with httpx.AsyncClient() as client:
        for i in range(0, len(data), max_records_per_request):
            batch = data[i:i + max_records_per_request]
            payload = {
                "records": [
                    {
                        "fields": record  # Map object directly to fields
                    }
                    for record in batch
                ]
            }

            try:
                response = await client.post(
                    f"https://api.airtable.com/v0/{base_id}/{table_id}",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 200:
                    # record_ids = [r["id"] for r in response.json().get("records", [])]
                    # created_records.extend(record_ids)
                    print(f"Created records",i)
                else:
                    error_details = response.json().get("error", {})
                    error_message = error_details.get("message", "Unknown error")
                    return {
                        "error": f"Failed to create records: {error_message}",
                        "status": response.status_code
                    }
            except httpx.RequestError as e:
                return {"error": f"Network error: {str(e)}"}

    return response
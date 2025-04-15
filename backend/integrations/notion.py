# notion.py

import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = 'your_client_id'
CLIENT_SECRET = "your_client_seceret"
REDIRECT_URI = 'http://localhost:8000/integrations/notion/oauth2callback'
authorization_url = f"https://api.notion.com/v1/oauth/authorize?client_id={CLIENT_ID}&response_type=code&owner=user&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fintegrations%2Fnotion%2Foauth2callback"

async def authorize_notion(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'notion_state:{org_id}:{user_id}', encoded_state, expire=600)

    return f'{authorization_url}&state={encoded_state}'

async def oauth2callback_notion(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(encoded_state)

    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'notion_state:{org_id}:{user_id}')

    if not saved_state :
        raise HTTPException(status_code=400, detail='State does not match.')

    encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.notion.com/v1/oauth/token',
            json={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI
            },
            headers={
                'Authorization': f'Basic {encoded_client_id_secret}',
                'Content-Type': 'application/json',
            }
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json().get('error', 'Unknown error'))

        await add_key_value_redis(
            f'notion_credentials:{org_id}:{user_id}',
            json.dumps(response.json()),
            expire=600
        )
        await delete_key_redis(f'notion_state:{org_id}:{user_id}')

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_notion_credentials(user_id, org_id):
    credentials = await get_value_redis(f'notion_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    
    await delete_key_redis(f'notion_credentials:{org_id}:{user_id}')
    return credentials

def _recursive_dict_search(data, target_key):
    """Recursively search for a key in a dictionary of dictionaries."""
    if target_key in data:
        return data[target_key]

    for value in data.values():
        if isinstance(value, dict):
            result = _recursive_dict_search(value, target_key)
            if result is not None:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _recursive_dict_search(item, target_key)
                    if result is not None:
                        return result
    return None

def create_integration_item_metadata_object(response_json: dict) -> IntegrationItem:
    """Creates an integration metadata object from a Notion API response."""

    # Extract title/content
    name = None
    if response_json.get('object') == 'database':
        title_data = response_json.get('title', [])
        if title_data and isinstance(title_data, list):
            name = title_data[0].get('plain_text')
    elif response_json.get('object') == 'page':
        name = _recursive_dict_search(response_json.get('properties', {}), 'plain_text')

    name = name or 'Untitled'
    name = f"{response_json['object'].capitalize()}: {name}"

    # Parent and parent type
    parent_data = response_json.get('parent', {})
    parent_type = parent_data.get('type')
    parent_id = None
    if parent_type and parent_type != 'workspace':
        parent_id = parent_data.get(parent_type)

    # Build IntegrationItem object
    integration_item_metadata = IntegrationItem(
        id=response_json.get('id'),
        type=response_json.get('object'),
        directory=(response_json['object'] == 'database'),  # databases are like folders
        parent_id=parent_id,
        parent_path_or_name=parent_type,
        name=name,
        creation_time=response_json.get('created_time'),
        last_modified_time=response_json.get('last_edited_time'),
        url=response_json.get('url'),
        mime_type=None,  # Notion doesn't expose this directly
        visibility=not response_json.get('archived', False),
    )

    return integration_item_metadata

async def get_items_notion(credentials) -> list[IntegrationItem]:
    """Aggregates all metadata relevant for a notion integration"""
    credentials = json.loads(credentials)
    list_of_integration_item_metadata = []
    response = requests.post(
        'https://api.notion.com/v1/search',
        headers={
            'Authorization': f'Bearer {credentials.get("access_token")}',
            'Notion-Version': '2022-06-28',
        },
    )

    if response.status_code == 200:
        results = response.json()['results']
        for result in results:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(result)
            )        

    return list_of_integration_item_metadata
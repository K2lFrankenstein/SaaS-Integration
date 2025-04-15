# 🔗 SaaS Integration Platform

## 📌 Project Overview

This project is a **SaaS Integration Hub** that enables users to **connect, visualize, and transfer data** between multiple platforms, including **HubSpot**, **Notion**, and **Airtable**.

It provides a unified interface to:
- Authenticate via OAuth
- Normalize data from different APIs
- Display it in a modern UI
- Transfer records across platforms with ease

---
&nbsp;

## 🚀 Features

1. **Secure Authentication**
   - **OAuth for Notion**: Implements OAuth flow (via `/oauth2callback_notion`) to securely connect user accounts.
   - **API Tokens**: Uses access tokens for HubSpot and Airtable, ensuring authorized data access.
   - **Impact**: Enables personalized, secure integrations without compromising user data.

2. **Data Fetching**
   - **Airtable Metadata**: Retrieves bases and tables using `/v0/meta/bases` and `/v0/meta/bases/{base_id}/tables`, structuring data as `IntegrationItem` objects.
   - **Use Case**: Identifies target tables (e.g., `tblNLBhL0YkldMTB7`) for record creation.
   - **Impact**: Lays the groundwork for dynamic data routing.

3. **Data Transformation**
   - **Field Mapping**: Aligns data with target schemas:
     - Filters invalid fields (e.g., `"id"`, `"visibility"`, `"directory"`) to prevent Airtable 422 errors.
     - Maps keys (e.g., `"visibility"` to “Is Visible”) for compatibility.
   - **Boolean Handling**: Supports `true`/`false` for Airtable checkbox fields or converts to text (“Yes”/“No”).
   - **Impact**: Ensures data fits each platform’s requirements, enhancing reliability.

4. **Data Transfer**
   - **Notion**:
     - Appends blocks to pages (`/v1/blocks/{page_id}/children`) or creates new pages (`/v1/pages`).
     - Splits large data (e.g., 4825 chars) into 2000-char blocks.
     - Example: Adds paragraphs like `{"id": "60302496472", "type": "company"}`.
   - **HubSpot**:
     - Transfers CRM data (e.g., contacts) via `/crm/v3/objects/contacts`.
     - Sends complex payloads using `FormData`.
   - **Airtable**:
     - Creates records in tables (`/v0/{base_id}/{table_id}`) with batching (10 records/request).
     - Example: Adds `{ "Name": "Demo Item", "Notes": "POC test" }`.
   - **Impact**: Demonstrates cross-platform data flow, validated in real-time.

5. **Error Handling and Feedback**
   - **API Errors**:
     - Notion: Manages 400 errors (e.g., invalid `rich_text`).
     - Airtable: Resolves 422 errors for unknown fields.
     - HubSpot: Handles credential and transfer failures.
   - **Feedback**:
     - Frontend alerts: “Success” or “Failed to create records”.
     - Backend logs: Detailed payloads and errors.
   - **Impact**: Builds user trust with clear, actionable feedback.

6. **Batch Processing**
   - Respects API limits:
     - Airtable: 10 records per request.
     - Notion: 2000 characters per block.
   - **Impact**: Scales to handle larger datasets efficiently.

---
&nbsp;

## 🧱 Tech Stack

### Frontend
| Technology     | Purpose                         |
|----------------|---------------------------------|
| React.js       | Component-based SPA             |
| Material UI    | Prebuilt UI components          |
| Axios          | HTTP client for API requests    |

### Backend
| Technology     | Purpose                         |
|----------------|---------------------------------|
| FastAPI-style  | Async backend (with `httpx`)    |
| Redis          | Store credentials and data      |
| Python + JSON  | Normalization + data transport  |

### Third-Party API Integrations
- **HubSpot CRM** (via `crm/v3/objects`)
- **Notion API** (pages, blocks, search)
- **Airtable API** (meta, records)

### Authentication:
- **OAuth**: Notion user authentication.
- **API Tokens**: HubSpot and Airtable access.
---

&nbsp;
## 📦 Data Model

### `IntegrationItem`

```python
class IntegrationItem:
    id: str    
    type: str
    directory: bool
    parent_path_or_name: str 
    parent_id: str 
    name: str
    creation_time: datetime 
    last_modified_time: datetime 
    url: str 
    children: List[str] 
    mime_type: str 
    delta: str 
    drive_id: str 
    visibility: bool 
```

All external platform data is normalized into this object for consistent processing and rendering.

--- 
&nbsp;

## 🔁 Data Flow

### 1. Authentication and Data Loading
To initiate integration, DataSync securely connects to platforms and prepares data for transfer:

- **OAuth Authentication**:
  - Users trigger OAuth from the frontend, opening a popup window (e.g., for Notion).
  - Upon approval, credentials are fetched and stored in Redis with a unique key:
    ```
    redis_key = f"{user_id}:{org_id}:{platform}"
    ```
- **Data Fetching**:
  - Data is retrieved based on the platform:
  - **HubSpot**: Fetches contacts and companies using pagination to handle large datasets.
  - **Notion**: Queries pages via the search API.
  - **Airtable**: Retrieves bases and tables to identify target schemas.
  - Fetched data is cached for efficient processing.
&nbsp;
- **Demo: GIF showing OAuth popup and data loading from HubSpot, Notion, and Airtable.**
  
![Hubspot|200x200](https://github.com/user-attachments/assets/686cd821-6ad3-4f0b-b0f8-f086c3624e38)
### <div align="center"> HubSpot </div>  

![Airtable|200x200](https://github.com/user-attachments/assets/881d7fac-f138-45ac-bb12-0b6b5c1d83a8)
### <div align="center"> Airtable </div>  

![Notion|200x200](https://github.com/user-attachments/assets/7a4b193a-437d-4645-b01d-e31f4da6cfa9)
### <div align="center"> Notion </div>  


  

### 2. Data Transfer
Once data is ready, users can transfer it to target platforms with a single request:

- **HubSpot Preparation**:
  - Data (e.g., contacts) is loaded from cache, ensuring quick access.
- **Notion Transfer**:
  - Data is posted as paragraphs to a Notion page block.
  - Large datasets are split to respect the 2000-character limit per block.
- **Airtable Transfer**:
  - Data is batched (10 records per request) and posted as records to a specified table.
  - Fields like `"visibility"` and `"directory"` are filtered or mapped to match table schemas.

&nbsp;

**Demo: GIF showing data transfer to Notion blocks and Airtable records.**

![Transfer Data - Airtable|200x200](https://github.com/user-attachments/assets/e6c5ad02-e372-448c-9140-a1b3d79dfe6e)
### <div align="center"> HubSpot --> Airtable </div>  


### <div align="center"> HubSpot --> Notion </div>  
---
&nbsp;

## Challenges Faced and Overcome

The POC tackled several technical hurdles, each resolved to ensure a robust demo:

1. **Notion API Constraints**:
   - **Challenge**: 400 Bad Request errors due to:
     - Invalid `rich_text` (e.g., sending lists instead of strings).
     - 2000-character limit per block (e.g., 4825-char JSON data).
     - OAuth setup complexity for `/oauth2callback_notion`.
   - **Solution**:
     - Validated payloads to ensure `rich_text` is a string.
     - Split large data into multiple blocks (e.g., 3 blocks for 4825 chars).
     - Implemented OAuth flow with secure token storage.
   - **Impact**: Reliable Notion page creation and block appending.

2. **HubSpot Data Transfer Issues**:
   - **Challenge**: Failed transfers due to:
     - Incorrect `FormData` parsing (e.g., `target_credentials`).
     - Invalid or missing tokens causing 401/400 errors.
   - **Solution**:
     - Debugged `FormData` with console logs to verify payloads.
     - Ensured `target_credentials` was properly JSON-stringified.
     - Added error handling for detailed feedback (e.g., “Invalid token”).
   - **Impact**: Successful contact creation in HubSpot CRM.

3. **Airtable Schema Validation**:
   - **Challenge**: 422 Unprocessable Entity errors for unknown fields:
     - `"id"`, `"visibility"`, and `"directory"` not in table schema.
     - Boolean values (`true`/`false`) potentially mismatched with text fields.
   - **Solution**:
     - Filtered invalid fields using a `valid_fields` list (e.g., `["Name", "Notes"]`).
     - Mapped `"visibility"` and `"directory"` to checkbox fields (e.g., “Is Visible”).
     - Provided fallback to convert booleans to text (“Yes”/“No”) if needed.
   - **Impact**: Error-free record creation in Airtable tables.

4. **API Limits and Performance**:
   - **Challenge**:
     - Airtable’s 10-record limit per request.
     - Notion’s 2000-char limit per block.
     - Potential rate limits (e.g., Airtable’s 5 requests/second).
   - **Solution**:
     - Implemented batching (e.g., 10 records per Airtable POST).
     - Split Notion content into compliant blocks.
     - Used async `httpx` for efficient API calls.
   - **Impact**: Scaled to handle realistic data volumes without throttling.

---
&nbsp;

## Getting Started

### Prerequisites
- Python 3.8+
- Redis server
- Node.js (for frontend)
- API keys/tokens for Notion, HubSpot, Airtable
- FastAPI dependencies: `fastapi`, `httpx`, `uvicorn`

### Installation

### Step-by-Step Installation

1. **Download and Extract the Project**
   ```bash
   # Download the project zip (replace with actual URL if available)
   curl -LO https://example.com/project.zip
   
   # Unzip the project
   unzip project.zip -d project-folder
   ```

2. **Backend Setup**
   ```bash
   # Navigate to backend directory
   cd project-folder/backend
   
   # Install Python dependencies (recommended to use a virtual environment)
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   # Navigate to frontend directory
   cd ../frontend
   
   # Install Node.js dependencies
   npm install
   ```

4. **Redis Setup**
   ```bash
   # Recommended method using Docker
   docker-compose up -d
   
   # Alternative method if Redis is installed locally
   redis-server
   ```

### Running the Application

You'll need three terminal windows/tabs open:

1. **Backend Server**
   ```bash
   cd project-folder/backend
   uvicorn main:app --reload
   ```
   - The backend will typically run at `http://localhost:8000`
   - `--reload` enables auto-reload during development

2. **Redis Server**
   ```bash
   # If using Docker (recommended)
   docker-compose up
   
   # If running locally
   redis-server
   ```

3. **Frontend Development Server**
   ```bash
   cd project-folder/frontend
   npm run start
   ```
   - The frontend will typically open at `http://localhost:3000`

### Verification
- Check backend: Visit `http://localhost:8000/docs` (should show Swagger/OpenAPI docs)
- Check frontend: Visit `http://localhost:3000`
- Check Redis: Run `redis-cli ping` (should respond with "PONG")

### Troubleshooting
- If port conflicts occur, check which ports (8000, 3000, 6379) are in use
- Ensure all services are using compatible versions as specified in package.json and requirements.txt
- For Windows users, use PowerShell or WSL for better compatibility with Unix commands

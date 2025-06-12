import os
import asyncio
import httpx
from fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
 
# --- Pydantic Models for Input Validation ---
class ProcessStatus(BaseModel):
    completed: str = Field(..., description="Process completion status")
    isMemput: str = Field(..., description="Member put status")
    errorCode: Optional[str] = Field(None, description="Error code if any")
    errorText: Optional[str] = Field(None, description="Error text if any")

class Address(BaseModel):
    type: str = Field(..., description="Address type")
    zip: Optional[str] = Field(None, description="ZIP code")

class Consumer(BaseModel):
    firstName: str = Field(..., description="First name")
    lastName: str = Field(..., description="Last name")
    middleName: Optional[str] = Field(None, description="Middle name")
    sex: str = Field(..., description="Gender")
    dob: str = Field(..., description="Date of birth")
    addressList: List[Address] = Field(..., description="List of addresses")
    id: Dict[str, Optional[str]] = Field(..., description="Identification information")

class SearchSetting(BaseModel):
    minScore: str = Field(..., description="Minimum score")
    maxResult: str = Field(..., description="Maximum results")

class MCIDRequestBody(BaseModel):
    requestID: str = Field(..., description="Request ID")
    processStatus: ProcessStatus = Field(..., description="Process status")
    consumer: List[Consumer] = Field(..., description="Consumer information")
    searchSetting: SearchSetting = Field(..., description="Search settings")

class MedicalRequestBody(BaseModel):
    requestID: str = Field(..., description="Request ID")
    firstName: str = Field(..., description="First name")
    lastName: str = Field(..., description="Last name")
    ssn: str = Field(..., description="Social Security Number")
    dateOfBirth: str = Field(..., description="Date of birth")
    gender: str = Field(..., description="Gender")
    zipCodes: List[str] = Field(..., description="List of ZIP codes")
    callerId: str = Field(..., description="Caller ID")

# --- Configuration (env overrideable) ---
TOKEN_URL = os.getenv(
    "TOKEN_URL",
    "XXXX"
)
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': os.getenv("CLIENT_ID", 'MILLIMAN'),
    'client_secret': os.getenv(
        "CLIENT_SECRET",
        'XXXX'
    )
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
MCID_URL = os.getenv(
    "MCID_URL",
    "XXXX"
)
MEDICAL_URL = os.getenv(
    "MEDICAL_URL",
    "XXXX"
)
 
# --- Default bodies for /all ---
MCID_REQUEST_BODY = {
    "requestID": "1",
    "processStatus": {"completed": "false", "isMemput": "false", "errorCode": None, "errorText": None},
    "consumer": [{"firstName": "XX", "lastName": "XXX", "middleName": None, "sex": "X", "dob": "XXXX",
                  "addressList": [{"type": "P", "zip": None}], "id": {"ssn": None}}],
    "searchSetting": {"minScore": "100", "maxResult": "1"}
}
MEDICAL_REQUEST_BODY = {
    "requestID": "",
    "firstName": "",
    "lastName": "",
    "ssn": "",
    "dateOfBirth": "",
    "gender": "",
    "zipCodes": ["", "", ""],
    "callerId": ""
}
 
# --- FastMCP setup ---
mcp = FastMCP(name="Milliman Dashboard Tools")
 
@mcp.tool(name="get_token", description="Fetch OAuth2 access token (no input)")
async def get_token_tool() -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)} 
 
@mcp.tool(
    name="mcid_search", 
    description="Perform MCID search with validated input"
)
async def mcid_search_tool(request_body: MCIDRequestBody) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(
                MCID_URL,
                headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
                json=request_body.model_dump()
            )
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}
 
@mcp.tool(
    name="submit_medical", 
    description="Submit medical eligibility with validated input"
)
async def submit_medical_tool(request_body: MedicalRequestBody) -> dict:
    token_result = await get_token_tool()
    if token_result.get('status_code') != 200:
        return {'status_code': 401, 'error': 'Failed to get access token'}
    
    token = token_result.get('body', {}).get('access_token')
    if not token:
        return {'status_code': 401, 'error': 'No access token in response'}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                MEDICAL_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=request_body.model_dump()
            )
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}
 
# --- Root FastAPI app with MCP routes included ---
app = FastAPI(
    title="Milliman Dashboard",
    description="FastMCP + FastAPI combined",
    version="0.0.1",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
# Include all FastMCP routes: /tool/{tool}, /prompt/{prompt}, /messages
app.mount("/",mcp.sse_app())
 
@app.get("/all")
async def call_all():
    """Run get_token, mcid_search and submit_medical with defaults."""
    try:
        token_task = get_token_tool()
        mcid_task = mcid_search_tool(MCIDRequestBody(**MCID_REQUEST_BODY))
        medical_task = submit_medical_tool(MedicalRequestBody(**MEDICAL_REQUEST_BODY))
        token_res, mcid_res, med_res = await asyncio.gather(token_task, mcid_task, medical_task)
        return {
            "get_token": token_res,
            "mcid_search": mcid_res,
            "submit_medical": med_res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
if __name__ == "__main__":
    mcp.run(transport="sse")

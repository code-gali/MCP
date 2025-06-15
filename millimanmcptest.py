import os
import asyncio
import httpx
from fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

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
    fname: str = Field(..., description="First name")
    lname: str = Field(..., description="Last name")
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
    requestId: str = Field(..., description="Request ID")
    firstName: str = Field(..., description="First name")
    lastName: str = Field(..., description="Last name")
    ssn: str = Field(..., description="Social Security Number")
    dateOfBirth: str = Field(..., description="Date of birth")
    gender: str = Field(..., description="Gender")
    zipCodes: List[str] = Field(..., description="List of ZIP codes")
    callerId: str = Field(..., description="Caller ID")

# --- Configuration ---
TOKEN_URL = os.getenv("TOKEN_URL", "XXXX")
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': os.getenv("CLIENT_ID", 'MILLIMAN'),
    'client_secret': os.getenv("CLIENT_SECRET", 'XXXX')
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
MCID_URL = os.getenv("MCID_URL", "XXXX")
MEDICAL_URL = os.getenv("MEDICAL_URL", "XXXX")

# --- FastMCP setup ---
mcp = FastMCP(name="Milliman Dashboard Tools")

# --- Helper function (used instead of calling get_token_tool directly) ---
async def _fetch_token() -> Optional[str]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            if response.status_code == 200:
                return response.json().get("access_token")
        except Exception as e:
            print(f"Token fetch error: {e}")
    return None

# --- Tools ---
@mcp.tool(name="get_token", description="Fetch OAuth2 access token (no input)")
async def get_token_tool() -> dict:
    token = await _fetch_token()
    if token:
        return {"status_code": 200, "body": {"access_token": token}}
    else:
        return {"status_code": 500, "error": "Failed to fetch token"}

@mcp.tool(name="mcid_search", description="Perform MCID search with validated input")
async def mcid_search_tool(request_body: MCIDRequestBody) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(
                MCID_URL,
                headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
                json=request_body.model_dump()
            )
            return {
                'status_code': response.status_code,
                'body': response.json() if response.content else {}
            }
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

@mcp.tool(name="submit_medical", description="Submit medical eligibility with validated input")
async def submit_medical_tool(request_body: MedicalRequestBody) -> dict:
    token = await _fetch_token()
    if not token:
        return {'status_code': 401, 'error': 'Failed to get access token'}

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
            return {
                'status_code': response.status_code,
                'body': response.json() if response.content else {}
            }
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

# --- FastAPI setup ---
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

# --- Mount MCP tools as server ---
app.mount("/", mcp.sse_app())

# --- Optional test route to run all (can be removed) ---
@app.get("/all")
async def call_all():
    try:
        token_task = _fetch_token()  # ✅ Use helper directly
        empty_mcid_body = MCIDRequestBody(
            requestID="1",
            processStatus=ProcessStatus(completed="false", isMemput="false"),
            consumer=[Consumer(
                fname="",
                lname="",
                sex="",
                dob="",
                addressList=[Address(type="P", zip=None)],
                id={"ssn": None}
            )],
            searchSetting=SearchSetting(minScore="100", maxResult="1")
        )
        empty_medical_body = MedicalRequestBody(
            requestId="REQ-TEST",
            firstName="",
            lastName="",
            ssn="",
            dateOfBirth="",
            gender="",
            zipCodes=["23060", "23229", "23242"],
            callerId="Milliman-Test16"
        )
        mcid_task = mcid_search_tool(empty_mcid_body)
        medical_task = submit_medical_tool(empty_medical_body)
        token_res, mcid_res, med_res = await asyncio.gather(token_task, mcid_task, medical_task)
        return {
            "get_token": {"access_token": token_res},
            "mcid_search": mcid_res,
            "submit_medical": med_res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Entry point ---
if __name__ == "__main__":
    mcp.run(transport="sse")

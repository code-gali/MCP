from fastapi import FastAPI, HTTPException
import httpx
import requests
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware

#app = FastAPI()

# FastAPI app initialization
app = FastAPI(
    title="Milliman Dashboard",
    description="The service routes chat messages to various chatbots.",
    version="0.0.1",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Hardcoded payloads ---
MCID_REQUEST_BODY = {
    "requestID": "1",
    "processStatus": {
        "completed": "false",
        "isMemput": "false",
        "errorCode": None,
        "errorText": None
    },
    "consumer": [
        {
            "fname": "APRIL",
            "lname": "MAY",
            "sex": "F",
            "dob": "XXXX",
            "addressList": [
                {
                    "type": "P",
                    "zip": None
                }
            ],
            "id": {
                "ssn": None
            }
        }
    ],
    "searchSetting": {
        "minScore": "100",
        "maxResult": "1"
    }
}

MEDICAL_REQUEST_BODY = {
    "requestId": "XXXX",
    "firstName": "XXXX",
    "lastName": "XXXX",
    "ssn": "XXXX",
    "dateOfBirth": "XXXX-XX-XX",
    "gender": "X",
    "zipCodes": [
        "23060",
        "23229",
        "23242"
    ],
    "callerId": "XXXXX"
}

TOKEN_URL = "XXXX"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'XXXX'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

# --- Individual API call functions ---

async def async_get_token():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

def get_access_token_sync():
    try:
        response = requests.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception:
        return None

async def async_submit_medical_request():
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {'status_code': 500, 'error': 'Access token not found'}
    medical_url = 'XXXX'
    payload = json.dumps({
    "requestId": "XXXX",
    "firstName": "XXXX",
    "lastName": "XXXX",
    "ssn": "XXXX",
    "dateOfBirth": "XXXX-XX-XX",
    "gender": "X",
    "zipCodes": [
        "23060",
        "23229",
        "23242"
        ],
    "callerId": "Milliman-Test16"})
    headers = {
    'Authorization': f'{access_token}',
    'content-type': 'application/json'
    }
    response = requests.request("POST", medical_url, headers=headers, data=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    #return response.json()
    return {'status_code':response.status_code}

async def async_mcid_search():
    url = "XXXX"
    headers = {
        'Content-Type': 'application/json',
        'Apiuser': 'MillimanUser'
    }
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=MCID_REQUEST_BODY)
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

# --- Main endpoint ---

@app.get("/all")
async def call_all():
    try:
        token_task = async_get_token()
        mcid_task = async_mcid_search()
        medical_task = async_submit_medical_request()
        token_result, mcid_result, medical_result = await asyncio.gather(token_task, mcid_task, medical_task)
        return {
            "get_token": token_result,
            "mcid_search": mcid_result,
            "medical_submit": medical_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
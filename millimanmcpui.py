import streamlit as st
import httpx
import asyncio
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Milliman MCP Tools Test",
    page_icon="🧪",
    layout="wide"
)

# Title and description
st.title("🧪 Milliman MCP Tools Test Interface")
st.markdown("""
This interface allows you to test the Milliman MCP tools:
- Get Token
- MCID Search
- Submit Medical
""")

# Initialize session state for storing token
if 'access_token' not in st.session_state:
    st.session_state.access_token = None

# Server configuration
SERVER_URL = "http://localhost:8000"

# Function to make async HTTP requests
async def make_request(url, method="GET", headers=None, data=None, json_data=None):
    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=headers)
        else:
            response = await client.post(url, headers=headers, data=data, json=json_data)
        return response

# Get Token Tool
st.header("1. Get Token")
if st.button("Get Token"):
    with st.spinner("Getting token..."):
        try:
            response = asyncio.run(make_request(
                url=f"{SERVER_URL}/tool/get_token",
                method="POST"
            ))
            if response.status_code == 200:
                st.session_state.access_token = response.json().get('body', {}).get('access_token')
                st.success("Token obtained successfully!")
                st.json(response.json())
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# MCID Search Tool
st.header("2. MCID Search")
with st.form("mcid_search_form"):
    st.subheader("Consumer Information")
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name", key="mcid_first_name")
        sex = st.selectbox("Gender", ["M", "F"], key="mcid_sex")
        ssn = st.text_input("SSN", key="mcid_ssn")
    with col2:
        last_name = st.text_input("Last Name", key="mcid_last_name")
        dob = st.date_input("Date of Birth", key="mcid_dob")
        zip_code = st.text_input("ZIP Code", key="mcid_zip")
    
    submitted = st.form_submit_button("Search MCID")
    
    if submitted:
        with st.spinner("Searching MCID..."):
            try:
                mcid_data = {
                    "requestID": "1",
                    "processStatus": {
                        "completed": "false",
                        "isMemput": "false",
                        "errorCode": None,
                        "errorText": None
                    },
                    "consumer": [{
                        "firstName": first_name,
                        "lastName": last_name,
                        "sex": sex,
                        "dob": dob.strftime("%Y-%m-%d"),
                        "addressList": [{
                            "type": "P",
                            "zip": zip_code
                        }],
                        "id": {
                            "ssn": ssn
                        }
                    }],
                    "searchSetting": {
                        "minScore": "0",
                        "maxResult": "1"
                    }
                }
                
                response = asyncio.run(make_request(
                    url=f"{SERVER_URL}/tool/mcid_search",
                    method="POST",
                    json_data=mcid_data
                ))
                
                if response.status_code == 200:
                    st.success("MCID Search completed successfully!")
                    st.json(response.json())
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Submit Medical Tool
st.header("3. Submit Medical")
with st.form("medical_submit_form"):
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name", key="med_first_name")
        ssn = st.text_input("SSN", key="med_ssn")
        gender = st.selectbox("Gender", ["M", "F"], key="med_gender")
    with col2:
        last_name = st.text_input("Last Name", key="med_last_name")
        dob = st.date_input("Date of Birth", key="med_dob")
        caller_id = st.text_input("Caller ID", key="med_caller_id")
    
    st.subheader("ZIP Codes")
    col3, col4, col5 = st.columns(3)
    with col3:
        zip1 = st.text_input("ZIP Code 1", key="med_zip1")
    with col4:
        zip2 = st.text_input("ZIP Code 2", key="med_zip2")
    with col5:
        zip3 = st.text_input("ZIP Code 3", key="med_zip3")
    
    submitted = st.form_submit_button("Submit Medical")
    
    if submitted:
        with st.spinner("Submitting medical information..."):
            try:
                medical_data = {
                    "requestID": str(datetime.now().timestamp()),
                    "firstName": first_name,
                    "lastName": last_name,
                    "ssn": ssn,
                    "dateOfBirth": dob.strftime("%Y-%m-%d"),
                    "gender": gender,
                    "zipCodes": [zip1, zip2, zip3],
                    "callerId": caller_id
                }
                
                response = asyncio.run(make_request(
                    url=f"{SERVER_URL}/tool/submit_medical",
                    method="POST",
                    json_data=medical_data
                ))
                
                if response.status_code == 200:
                    st.success("Medical submission completed successfully!")
                    st.json(response.json())
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Run all tools
st.header("4. Run All Tools")
if st.button("Run All Tools"):
    with st.spinner("Running all tools..."):
        try:
            response = asyncio.run(make_request(
                url=f"{SERVER_URL}/all",
                method="GET"
            ))
            if response.status_code == 200:
                st.success("All tools executed successfully!")
                st.json(response.json())
            else:
                st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Add some styling
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .stForm {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True) 

import streamlit as st
import httpx
import asyncio
import json
from datetime import datetime
from mcp.client.sse import sse_client
from mcp import ClientSession

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
SERVER_URL = "http://localhost:8000/sse"

# Function to call MCP tools using client session
async def call_mcp_tool(tool_name, arguments=None):
    try:
        async with sse_client(url=SERVER_URL) as sse:
            async with ClientSession(*sse) as session:
                await session.initialize()
                result = await session.call_tool(name=tool_name, arguments=arguments)
                return result
    except Exception as e:
        return {"error": str(e)}

# Get Token Tool
st.header("1. Get Token")
if st.button("Get Token"):
    with st.spinner("Getting token..."):
        try:
            result = asyncio.run(call_mcp_tool("get_token"))
            if not result.get("error"):
                st.session_state.access_token = result.get('body', {}).get('access_token')
                st.success("Token obtained successfully!")
                st.json(result)
            else:
                st.error(f"Error: {result.get('error')}")
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
                
                result = asyncio.run(call_mcp_tool("mcid_search", mcid_data))
                
                if result.get("error"):
                    st.error(f"Error: {result.get('error')}")
                else:
                    st.success("MCID Search completed successfully!")
                    st.json(result)
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
                
                result = asyncio.run(call_mcp_tool("submit_medical", medical_data))
                
                if result.get("error"):
                    st.error(f"Error: {result.get('error')}")
                else:
                    st.success("Medical submission completed successfully!")
                    st.json(result)
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Run all tools
st.header("4. Run All Tools")
if st.button("Run All Tools"):
    with st.spinner("Running all tools..."):
        try:
            result = asyncio.run(call_mcp_tool("all"))
            if result.get("error"):
                st.error(f"Error: {result.get('error')}")
            else:
                st.success("All tools executed successfully!")
                st.json(result)
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

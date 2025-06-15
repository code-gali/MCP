import streamlit as st
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
                # Convert the result to a dictionary if it's not already
                if hasattr(result, "model_dump"):
                    return result.model_dump()
                return result
    except Exception as e:
        return {"error": str(e)}

# Get Token Tool
st.header("1. Get Token")
if st.button("Get Token"):
    with st.spinner("Getting token..."):
        try:
            result = asyncio.run(call_mcp_tool("get_token"))
            if isinstance(result, dict) and "error" in result:
                st.error(f"Error: {result['error']}")
            else:
                # Handle the result based on its structure
                body = result.get('body', {}) if isinstance(result, dict) else {}
                if isinstance(body, dict):
                    st.session_state.access_token = body.get('access_token')
                st.success("Token obtained successfully!")
                st.json(result)
        except Exception as e:
            st.error(f"Error: {str(e)}")

# MCID Search Tool
st.header("2. MCID Search")
with st.form("mcid_search_form"):
    st.subheader("Consumer Information")
    col1, col2 = st.columns(2)
    with col1:
        fname = st.text_input("First Name*", key="mcid_fname", help="Enter first name (required)")
        sex = st.selectbox("Gender*", ["M", "F"], key="mcid_sex", help="Select gender (required)")
        ssn = st.text_input("SSN (Optional)", key="mcid_ssn", help="Enter SSN in format: XXX-XX-XXXX", placeholder="XXX-XX-XXXX")
    with col2:
        lname = st.text_input("Last Name*", key="mcid_lname", help="Enter last name (required)")
        dob = st.text_input("Date of Birth* (YYYY-MM-DD)", placeholder="YYYY-MM-DD", key="mcid_dob", help="Enter date in YYYY-MM-DD format (required)")
        zip_code = st.text_input("ZIP Code (Optional)", key="mcid_zip", help="Enter 5-digit ZIP code", placeholder="XXXXX")
    
    st.markdown("**Required fields are marked with *")
    
    submitted = st.form_submit_button("Search MCID")
    
    if submitted:
        # Validate inputs
        errors = []
        if not fname:
            errors.append("First name is required")
        if not lname:
            errors.append("Last name is required")
        if not sex:
            errors.append("Gender is required")
        if ssn and (not ssn.replace("-", "").isdigit() or len(ssn.replace("-", "")) != 9):
            errors.append("SSN must be in format: XXX-XX-XXXX")
        if not dob or not dob.replace("-", "").isdigit() or len(dob) != 10:
            errors.append("Date of birth must be in format: YYYY-MM-DD")
        if zip_code and (not zip_code.isdigit() or len(zip_code) != 5):
            errors.append("ZIP code must be 5 digits")
            
        if errors:
            for error in errors:
                st.error(error)
        else:
            with st.spinner("Searching MCID..."):
                try:
                    # Create request body matching FastAPI implementation
                    mcid_data = {
                        "requestID": "1",  # Match FastAPI's default
                        "processStatus": {
                            "completed": "false",
                            "isMemput": "false",
                            "errorCode": None,
                            "errorText": None
                        },
                        "consumer": [{
                            "fname": fname.upper(),  # Convert to uppercase as per API
                            "lname": lname.upper(),  # Convert to uppercase as per API
                            "sex": sex,
                            "dob": dob,
                            "addressList": [{
                                "type": "P",
                                "zip": zip_code if zip_code else None
                            }],
                            "id": {
                                "ssn": ssn.replace("-", "") if ssn else None
                            }
                        }],
                        "searchSetting": {
                            "minScore": "100",  # Match FastAPI's default
                            "maxResult": "1"    # Match FastAPI's default
                        }
                    }
                    
                    result = asyncio.run(call_mcp_tool("mcid_search", mcid_data))
                    
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Error: {result['error']}")
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
        first_name = st.text_input("First Name*", key="med_first_name", help="Enter first name (required)")
        ssn = st.text_input("SSN*", key="med_ssn", help="Enter SSN in format: XXX-XX-XXXX", placeholder="XXX-XX-XXXX")
        gender = st.selectbox("Gender*", ["M", "F"], key="med_gender", help="Select gender (required)")
    with col2:
        last_name = st.text_input("Last Name*", key="med_last_name", help="Enter last name (required)")
        dob = st.text_input("Date of Birth* (YYYY-MM-DD)", placeholder="YYYY-MM-DD", key="med_dob", help="Enter date in YYYY-MM-DD format (required)")
        caller_id = st.text_input("Caller ID*", key="med_caller_id", help="Enter caller ID (required)", placeholder="Milliman-Test16")
    
    st.subheader("ZIP Codes")
    col3, col4, col5 = st.columns(3)
    with col3:
        zip1 = st.text_input("ZIP Code 1*", key="med_zip1", help="Enter 5-digit ZIP code (required)", placeholder="23060")
    with col4:
        zip2 = st.text_input("ZIP Code 2*", key="med_zip2", help="Enter 5-digit ZIP code (required)", placeholder="23229")
    with col5:
        zip3 = st.text_input("ZIP Code 3*", key="med_zip3", help="Enter 5-digit ZIP code (required)", placeholder="23242")
    
    submitted = st.form_submit_button("Submit Medical")
    
    if submitted:
        # Validate inputs
        errors = []
        if not first_name:
            errors.append("First name is required")
        if not last_name:
            errors.append("Last name is required")
        if not ssn or not ssn.replace("-", "").isdigit() or len(ssn.replace("-", "")) != 9:
            errors.append("SSN must be in format: XXX-XX-XXXX")
        if not dob or not dob.replace("-", "").isdigit() or len(dob) != 10:
            errors.append("Date of birth must be in format: YYYY-MM-DD")
        if not gender:
            errors.append("Gender is required")
        if not caller_id:
            errors.append("Caller ID is required")
        if not zip1 or not zip1.isdigit() or len(zip1) != 5:
            errors.append("ZIP Code 1 must be 5 digits")
        if not zip2 or not zip2.isdigit() or len(zip2) != 5:
            errors.append("ZIP Code 2 must be 5 digits")
        if not zip3 or not zip3.isdigit() or len(zip3) != 5:
            errors.append("ZIP Code 3 must be 5 digits")
            
        if errors:
            for error in errors:
                st.error(error)
        else:
            with st.spinner("Submitting medical information..."):
                try:
                    # Create request body matching FastAPI implementation
                    medical_data = {
                        "requestId": "XXXX",  # Match FastAPI's default
                        "firstName": first_name.upper(),  # Convert to uppercase as per API
                        "lastName": last_name.upper(),    # Convert to uppercase as per API
                        "ssn": ssn.replace("-", ""),
                        "dateOfBirth": dob,
                        "gender": gender,
                        "zipCodes": [zip1, zip2, zip3],
                        "callerId": caller_id
                    }
                    
                    result = asyncio.run(call_mcp_tool("submit_medical", medical_data))
                    
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Error: {result['error']}")
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
            if isinstance(result, dict) and "error" in result:
                st.error(f"Error: {result['error']}")
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
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stForm {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stTextInput>div>div>input {
        border-radius: 4px;
    }
    .stSelectbox>div>div>select {
        border-radius: 4px;
    }
    .stMarkdown {
        color: #666;
    }
    .stError {
        color: #dc3545;
        font-weight: bold;
    }
    .stSuccess {
        color: #28a745;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True) 

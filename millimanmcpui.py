import streamlit as st
import asyncio
from datetime import datetime
from fastmcp.client import FastMCPClient
import httpx

# Page setup
st.set_page_config(page_title="Milliman MCP Tools Test", layout="wide")

st.title("🧪 Milliman MCP Tools Test UI")
st.markdown("This UI tests MCP tools over SSE using FastMCPClient.")

# Async tool caller
async def call_mcp_tool(tool_name: str, input_data: dict = None) -> dict:
    client = FastMCPClient("http://localhost:8000/sse")
    return await client.call_tool(tool_name, input_data)

# Section 1: Get Token
st.header("1️⃣ Get Token")
if st.button("Get Token"):
    with st.spinner("Fetching token from MCP..."):
        try:
            result = asyncio.run(call_mcp_tool("get_token"))
            token = result.get("body", {}).get("access_token")
            if token:
                st.success("Token fetched:")
                st.code(token)
            else:
                st.warning("No token found in response.")
            st.json(result)
        except Exception as e:
            st.error(f"Error: {e}")

# Section 2: MCID Search
st.header("2️⃣ MCID Search")
with st.form("mcid_form"):
    st.subheader("Consumer Info")
    col1, col2 = st.columns(2)
    with col1:
        first = st.text_input("First Name")
        sex = st.selectbox("Gender", ["M", "F"])
        ssn = st.text_input("SSN")
    with col2:
        last = st.text_input("Last Name")
        dob = st.date_input("DOB")
        zipc = st.text_input("ZIP Code")

    if st.form_submit_button("Search MCID"):
        with st.spinner("Running MCID search..."):
            payload = {
                "requestID": "1",
                "processStatus": {
                    "completed": "false",
                    "isMemput": "false",
                    "errorCode": None,
                    "errorText": None
                },
                "consumer": [{
                    "firstName": first,
                    "lastName": last,
                    "sex": sex,
                    "dob": dob.strftime("%Y-%m-%d"),
                    "addressList": [{"type": "P", "zip": zipc}],
                    "id": {"ssn": ssn}
                }],
                "searchSetting": {"minScore": "0", "maxResult": "1"}
            }
            try:
                result = asyncio.run(call_mcp_tool("mcid_search", payload))
                st.success("MCID search complete.")
                st.json(result)
            except Exception as e:
                st.error(f"Error: {e}")

# Section 3: Submit Medical
st.header("3️⃣ Submit Medical")
with st.form("med_form"):
    col1, col2 = st.columns(2)
    with col1:
        fname = st.text_input("First Name")
        ssn = st.text_input("SSN")
        gender = st.selectbox("Gender", ["M", "F"])
    with col2:
        lname = st.text_input("Last Name")
        dob = st.date_input("DOB")
        caller = st.text_input("Caller ID")

    st.subheader("ZIP Codes")
    z1, z2, z3 = st.columns(3)
    with z1:
        zip1 = st.text_input("ZIP 1")
    with z2:
        zip2 = st.text_input("ZIP 2")
    with z3:
        zip3 = st.text_input("ZIP 3")

    if st.form_submit_button("Submit Medical"):
        with st.spinner("Submitting medical request..."):
            med_payload = {
                "requestID": str(datetime.now().timestamp()),
                "firstName": fname,
                "lastName": lname,
                "ssn": ssn,
                "dateOfBirth": dob.strftime("%Y-%m-%d"),
                "gender": gender,
                "zipCodes": [zip1, zip2, zip3],
                "callerId": caller
            }
            try:
                result = asyncio.run(call_mcp_tool("submit_medical", med_payload))
                st.success("Medical request submitted.")
                st.json(result)
            except Exception as e:
                st.error(f"Error: {e}")

# Section 4: Run /all
st.header("4️⃣ Run All (Optional FastAPI Test)")
if st.button("Run /all endpoint"):
    with st.spinner("Calling /all FastAPI route..."):
        try:
            response = httpx.get("http://localhost:8000/all")
            st.success("Call completed.")
            st.json(response.json())
        except Exception as e:
            st.error(f"Error calling /all: {e}")

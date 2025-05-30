import streamlit as st
import requests
import pandas as pd
import json

# MCP server endpoint (your FastAPI server)
MCP_URL = "http://localhost:8000/tool/analyze-data"

# Page setup
st.set_page_config(page_title="📊 MCP JSON Analyzer Client", layout="wide")
st.title("📊 JSON Column Analyzer via MCP Server")

# Upload JSON file
uploaded_file = st.file_uploader("📁 Upload a JSON file (list of objects)", type=["json"])

if uploaded_file:
    try:
        # Parse the uploaded JSON
        json_data = json.load(uploaded_file)
        if isinstance(json_data, list) and isinstance(json_data[0], dict):
            df = pd.DataFrame(json_data)

            # Show table preview
            st.subheader("👀 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            # Extract numeric columns
            numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()

            if not numeric_columns:
                st.warning("No numeric columns found.")
            else:
                selected_column = st.selectbox("🔢 Choose a numeric column", numeric_columns)
                operation = st.selectbox("⚙️ Choose operation", ["sum", "mean", "average", "median", "min", "max", "count"])

                if st.button("🚀 Run Analysis"):
                    with st.spinner("Calling MCP server..."):
                        try:
                            # POST request to MCP server
                            response = requests.post(
                                MCP_URL,
                                json={"data": json_data},  # send full JSON under 'data' key
                                timeout=10
                            )
                            if response.status_code == 200:
                                result = response.json()
                                if result.get("status") == "success":
                                    column_stats = result["result"]
                                    if selected_column in column_stats:
                                        val = column_stats[selected_column]
                                        st.success(f"✅ `{operation}` of **{selected_column}**: **{val:.2f}**")
                                    else:
                                        st.error(f"Column '{selected_column}' not found in server response.")
                                else:
                                    st.error(f"❌ Error: {result.get('error')}")
                            else:
                                st.error(f"❌ Server error: {response.status_code} - {response.text}")
                        except Exception as e:
                            st.error(f"❌ Request failed: {e}")
        else:
            st.error("Please upload a JSON array of objects.")
    except Exception as e:
        st.error(f"Invalid JSON file: {e}")
else:
    st.info("📤 Upload a JSON file to start.")

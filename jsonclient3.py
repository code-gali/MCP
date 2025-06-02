import streamlit as st
import requests
import json
import pandas as pd
import numpy as np
from typing import Any, Dict, List
from collections import defaultdict

# MCP server endpoint (FastAPI backend)
MCP_URL = "http://localhost:8000/tool/analyze-data"

# Page setup
st.set_page_config(page_title="📊 MCP JSON Analyzer Client", layout="wide")
st.title("📊 JSON Column Analyzer via MCP Server")

def extract_numeric_values(data: Any) -> Dict[str, List[float]]:
    """Extract all numeric values from nested JSON structure and aggregate by field name"""
    # Use defaultdict to automatically create lists for new keys
    result = defaultdict(list)
    
    def process_value(value: Any):
        if isinstance(value, dict):
            # Special handling for components
            if 'components' in value:
                components = value['components']
                if isinstance(components, list):
                    for comp in components:
                        if isinstance(comp, dict):
                            # Process component data
                            if 'data' in comp:
                                for data_item in comp['data']:
                                    if isinstance(data_item, dict):
                                        for k, v in data_item.items():
                                            if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(',', '').replace('.', '').isdigit()):
                                                try:
                                                    result[k].append(float(str(v).replace(',', '')))
                                                except (ValueError, TypeError):
                                                    pass
                            # Process other component fields
                            for k, v in comp.items():
                                if k != 'data' and (isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(',', '').replace('.', '').isdigit())):
                                    try:
                                        result[k].append(float(str(v).replace(',', '')))
                                    except (ValueError, TypeError):
                                        pass
            # Process other dictionary fields
            for k, v in value.items():
                if k != 'components':  # Skip components as we handled it above
                    process_value(v)
        elif isinstance(value, list):
            for v in value:
                process_value(v)
        else:
            # Handle numeric values
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace(',', '').replace('.', '').isdigit()):
                try:
                    # Use the last part of the path as the key
                    result['value'].append(float(str(value).replace(',', '')))
                except (ValueError, TypeError):
                    pass
    
    process_value(data)
    return dict(result)

def create_dataframe_from_numeric_values(all_numeric_values: Dict[str, List[float]]) -> pd.DataFrame:
    """Create a DataFrame from numeric values, handling different length arrays"""
    # Find the maximum length of any array
    max_length = max(len(values) for values in all_numeric_values.values())
    
    # Pad shorter arrays with None instead of NaN
    padded_values = {}
    for key, values in all_numeric_values.items():
        if len(values) < max_length:
            padded_values[key] = values + [None] * (max_length - len(values))
        else:
            padded_values[key] = values
    
    return pd.DataFrame(padded_values)

def prepare_data_for_server(df: pd.DataFrame, column: str) -> List[Dict]:
    """Prepare data for server by replacing NaN with None"""
    # Convert DataFrame to records and handle NaN values
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            value = row[col]
            # Convert NaN to None
            if pd.isna(value):
                record[col] = None
            else:
                record[col] = value
        records.append(record)
    return records

# Upload JSON file
uploaded_file = st.file_uploader("📁 Upload a JSON file", type=["json"])

if uploaded_file:
    try:
        # Load and parse JSON
        json_data = json.load(uploaded_file)
        
        # Process the JSON data
        all_numeric_values = extract_numeric_values(json_data)
        
        # Display extracted columns for debugging
        st.subheader("🔍 Extracted Columns")
        st.write("Found the following numeric columns:")
        for col, values in all_numeric_values.items():
            st.write(f"- {col}: {len(values)} values")
        
        # Create DataFrame from numeric values
        df = create_dataframe_from_numeric_values(all_numeric_values)
        
        # Display data preview
        st.subheader("👀 Data Preview")
        st.dataframe(df.head(), use_container_width=True)
        
        # Get numeric columns
        numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
        
        if not numeric_columns:
            st.warning("No numeric columns found in the data.")
        else:
            # Display numeric columns in a more organized way
            st.subheader("📊 Available Numeric Columns")
            
            # Create a DataFrame to display column information
            column_info = pd.DataFrame({
                'Column Name': numeric_columns,
                'Non-Null Count': [df[col].count() for col in numeric_columns],
                'Mean': [df[col].mean() for col in numeric_columns],
                'Min': [df[col].min() for col in numeric_columns],
                'Max': [df[col].max() for col in numeric_columns]
            })
            
            # Display column information
            st.dataframe(column_info, use_container_width=True)
            
            # Column selection with search
            selected_column = st.selectbox(
                "🔢 Select a numeric column to analyze",
                numeric_columns,
                help="Choose a column to perform operations on"
            )
            
            # Operation selection
            operation = st.selectbox(
                "⚙️ Select operation",
                ["sum", "mean", "average", "median", "min", "max", "count"],
                help="Choose the operation to perform on the selected column"
            )
            
            if st.button("🚀 Run Analysis"):
                with st.spinner("Analyzing..."):
                    try:
                        # Prepare data for server
                        server_data = prepare_data_for_server(df, selected_column)
                        
                        response = requests.post(
                            MCP_URL,
                            json={
                                "data": server_data,
                                "column": selected_column,
                                "operation": operation
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result["status"] == "success":
                                st.success(f"✅ {operation.title()} of {selected_column}: {result['value']:.2f}")
                                
                                # Display a histogram of the selected column
                                st.subheader("📈 Distribution of Selected Column")
                                # Remove NaN values before plotting
                                clean_data = df[selected_column].dropna()
                                if not clean_data.empty:
                                    st.bar_chart(clean_data.value_counts().sort_index())
                                else:
                                    st.warning("No valid data points to display in histogram.")
                            else:
                                st.error(f"❌ Error: {result.get('error')}")
                        else:
                            st.error(f"❌ Server error: {response.status_code}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Could not connect to server. Please make sure the server is running.")
                    except Exception as e:
                        st.error(f"❌ Error during analysis: {str(e)}")
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON file. Please upload a valid JSON file.")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
else:
    st.info("📤 Please upload a JSON file to begin analysis.")

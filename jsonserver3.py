from fastapi import FastAPI, Request
from typing import Any, Dict, List
from loguru import logger
import uvicorn
import pandas as pd
import numpy as np

app = FastAPI(title="Universal JSON Analyzer")

def extract_numeric_values(data: Any) -> Dict[str, float]:
    """Extract all numeric values from nested JSON structure"""
    result = {}
    
    def process_value(value: Any, path: str = ""):
        if isinstance(value, dict):
            for k, v in value.items():
                new_path = f"{path}.{k}" if path else k
                process_value(v, new_path)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                new_path = f"{path}[{i}]"
                process_value(v, new_path)
        else:
            try:
                # Try to convert to float, handling comma-separated numbers
                if isinstance(value, str):
                    value = value.replace(',', '')
                num_value = float(value)
                result[path] = num_value
            except (ValueError, TypeError):
                pass
    
    process_value(data)
    return result

def perform_column_operation(data: List[Dict], column: str, operation: str) -> float:
    """Perform the requested operation on the specified column"""
    try:
        # Extract numeric values from the data
        numeric_data = []
        for item in data:
            numeric_values = extract_numeric_values(item)
            if column in numeric_values:
                numeric_data.append(numeric_values[column])
        
        if not numeric_data:
            raise ValueError(f"No numeric values found for column '{column}'")
        
        # Convert to numpy array for calculations
        arr = np.array(numeric_data)
        
        if operation == "sum":
            return float(np.sum(arr))
        elif operation == "mean" or operation == "average":
            return float(np.mean(arr))
        elif operation == "median":
            return float(np.median(arr))
        elif operation == "min":
            return float(np.min(arr))
        elif operation == "max":
            return float(np.max(arr))
        elif operation == "count":
            return float(len(arr))
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    except Exception as e:
        logger.error(f"Error performing operation: {str(e)}")
        raise

@app.post("/tool/analyze-data")
async def analyze_json(request: Request):
    try:
        body = await request.json()
        data = body.get("data")
        column = body.get("column")
        operation = body.get("operation")
        
        if not data or not column or not operation:
            return {"status": "error", "error": "Missing required parameters: data, column, or operation"}
        
        result = perform_column_operation(data, column, operation)
        return {"status": "success", "value": result}
    except Exception as e:
        logger.exception("Analysis failed")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

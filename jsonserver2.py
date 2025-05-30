from fastapi import FastAPI, Request
from loguru import logger
from typing import Any, Dict, List
import uvicorn

app = FastAPI(title="Column-wise JSON Summation Server")

# --- Helper: Extract numeric values grouped by column (attribute) ---
def extract_column_wise_sums(data: Any, parent_key: str = "", result: Dict[str, float] = None) -> Dict[str, float]:
    if result is None:
        result = {}

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            extract_column_wise_sums(value, new_key, result)
    elif isinstance(data, list):
        for item in data:
            extract_column_wise_sums(item, parent_key, result)
    elif isinstance(data, (int, float)):
        result[parent_key] = result.get(parent_key, 0.0) + float(data)
    elif isinstance(data, str):
        try:
            result[parent_key] = result.get(parent_key, 0.0) + float(data)
        except ValueError:
            pass  # ignore non-numeric strings

    return result

# --- API Endpoint ---
@app.post("/tool/analyze-data")
async def analyze_column_data(request: Request):
    try:
        body = await request.json()
        data = body.get("data")
        column_sums = extract_column_wise_sums(data)

        if not column_sums:
            return {"status": "error", "error": "No numeric fields found."}

        return {"status": "success", "result": column_sums}

    except Exception as e:
        logger.exception("Failed to analyze data")
        return {"status": "error", "error": str(e)}

# --- Run the app ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

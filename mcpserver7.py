from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
 
 
import json
import statistics
import requests
from typing import Optional, Dict, List
from mcp.server.fastmcp import FastMCP
 
# --- App Initialization ---
app = FastAPI(title="MCP Data Utility App")
mcp = FastMCP("MCP Data Utility Context", app=app)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- Configurations ---
ENV = "preprod"
REGION_NAME = "us-east-1"
SENDER_EMAIL = 'AbhinavVarma.Lakamraju@elevancehealth.com'
 
# --- Health Check Endpoint ---
@app.get("/")
async def root():
    return {"message": "MCP Data Utility Server is running"}
 
# --- Email Tool ---
class EmailRequest(BaseModel):
    subject: str
    body: str
    receivers: str
 
@mcp.tool(name="mcp-send-email", description="Send an email with a subject and HTML body to recipients.")
def mcp_send_email(subject: str, body: str, receivers: str) -> Dict:
    try:
        recipients = [email.strip() for email in receivers.split(",")]
 
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = ', '.join(recipients)
        msg.attach(MIMEText(body, 'html'))
 
        smtp = get_ser_conn(logger, env=ENV, region_name=REGION_NAME, aplctn_cd="aedl", port=None, tls=True, debug=False)
        smtp.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        smtp.quit()
 
        logger.info("Email sent successfully.")
        return {"status": "success", "message": "Email sent successfully."}
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {"status": "error", "message": str(e)}
 
@app.post("/send_test_email")
def send_test_email(email_request: EmailRequest):
    return mcp_send_email(email_request.subject, email_request.body, email_request.receivers)
 
# --- MCP Tools ---
@mcp.tool(name="mcp-calculator", description="Evaluate a basic arithmetic expression with +, -, *, /, and parentheses.")
def mcp_calculator(expression: str) -> str:
    try:
        allowed_chars = "0123456789+-*/(). "
        if any(char not in allowed_chars for char in expression):
            return "Invalid characters in expression."
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"
 
@mcp.tool(name="mcp-json-analyzer", description="Analyze JSON numeric data: sum, mean, median, min, max.")
def mcp_json_analyzer(data: Dict[str, List[float]], operation: str) -> Dict:
    try:
        valid_ops = {"sum": sum, "mean": statistics.mean, "median": statistics.median, "min": min, "max": max}
        if operation not in valid_ops:
            return {"error": f"Unsupported operation: {operation}"}
 
        result = {}
        for key, values in data.items():
            if not isinstance(values, list):
                return {"error": f"Value for '{key}' must be a list"}
            numbers = [float(n) for n in values]
            if not numbers:
                return {"error": f"No numbers provided for '{key}'"}
            result[key] = valid_ops[operation](numbers)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"error": f"Error analyzing data: {str(e)}"}
@app.post("/api/mcp")
async def mcp_api(request: Request):
    try:
        body_bytes = await request.body()
        logger.info(f"Received request: {body_bytes[:200]}")
        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return JSONResponse(status_code=400, content={"status": "error", "error": f"Invalid JSON: {str(e)}"})
 
        if "data" not in data or "operation" not in data:
            return JSONResponse(status_code=400, content={"status": "error", "error": "Missing 'data' or 'operation' field"})
 
        input_data = data["data"]
        operation = data["operation"].lower()
        valid_operations = ["sum", "mean", "median", "min", "max"]
        if operation not in valid_operations:
            return JSONResponse(status_code=400, content={"status": "error", "error": f"Invalid operation. Use one of: {', '.join(valid_operations)}"})
 
        result = None
        try:
            if isinstance(input_data, list):
                numbers = [float(n) for n in input_data]
                if not numbers:
                    return JSONResponse(status_code=400, content={"status": "error", "error": "Empty data list"})
                result = {
                    "sum": sum(numbers),
                    "mean": statistics.mean(numbers),
                    "median": statistics.median(numbers),
                    "min": min(numbers),
                    "max": max(numbers)
                }[operation]
            elif isinstance(input_data, dict):
                results_dict = {}
                for key, values in input_data.items():
                    if not isinstance(values, list):
                        return JSONResponse(status_code=400, content={"status": "error", "error": f"Value for key '{key}' must be a list"})
                    numbers = [float(n) for n in values]
                    if not numbers:
                        return JSONResponse(status_code=400, content={"status": "error", "error": f"Empty data list for key '{key}'"})
                    results_dict[key] = {
                        "sum": sum(numbers),
                        "mean": statistics.mean(numbers),
                        "median": statistics.median(numbers),
                        "min": min(numbers),
                        "max": max(numbers)
                    }[operation]
                result = results_dict
            else:
                return JSONResponse(status_code=400, content={"status": "error", "error": f"Data must be a list or dictionary, got {type(input_data).__name__}"})
        except (ValueError, TypeError) as e:
            logger.error(f"Data processing error: {e}")
            return JSONResponse(status_code=400, content={"status": "error", "error": f"Data processing error: {str(e)}"})
 
        return {"status": "success", "result": result}
 
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"status": "error", "error": "Internal server error"})
   
@mcp.tool(name="mcp-get-weather", description="Fetch weather forecast from latitude and longitude using NWS API.")
def mcp_get_weather(latitude: float, longitude: float) -> str:
    try:
        headers = {
            "User-Agent": "MCP Weather Client (noreply@example.com)",
            "Accept": "application/geo+json"
        }
        points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        response = requests.get(points_url, headers=headers)
        response.raise_for_status()
        forecast_url = response.json()['properties']['forecast']
        city = response.json()['properties']['relativeLocation']['properties']['city']
        state = response.json()['properties']['relativeLocation']['properties']['state']
 
        forecast_resp = requests.get(forecast_url, headers=headers)
        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()['properties']['periods'][0]['detailedForecast']
 
        return f"Weather for {city}, {state}: {forecast_data}"
    except Exception as e:
        return f"Error fetching weather: {str(e)}"
 
# --- MCP Prompts ---
# HEDIS Application Prompts
@mcp.prompt(name="hedis.explain-bcs", description="Explain the BCS HEDIS measure.")
async def explain_bcs() -> str:
    print("\n📝 [HEDIS] BCS Prompt Called")
    return "Explain the purpose of the BCS HEDIS measure."

@mcp.prompt(name="hedis.list-2024", description="List HEDIS measures for 2024.")
async def list_hedis_2024() -> str:
    print("\n📝 [HEDIS] 2024 List Prompt Called")
    return "List all HEDIS measures for the year 2024."

@mcp.prompt(name="hedis.cbp-age", description="Get age criteria for CBP measure.")
async def cbp_age_criteria() -> str:
    print("\n📝 [HEDIS] CBP Age Criteria Prompt Called")
    return "What is the age criteria for the CBP HEDIS measure?"

# Contract Application Prompts
@mcp.prompt(name="contract.summarize-h123", description="Summarize contract ID H123.")
async def summarize_contract() -> str:
    print("\n📝 [CONTRACT] H123 Summary Prompt Called")
    return "Summarize contract ID H123 for 2023."

@mcp.prompt(name="contract.compare", description="Compare contracts H456 and H789.")
async def compare_contracts() -> str:
    print("\n📝 [CONTRACT] Comparison Prompt Called")
    return "Compare contracts H456 and H789 on key metrics."

# Original MCP Prompts
@mcp.prompt(name="mcp-prompt-calculator", description="Prompt template for calculator use case.")
async def mcp_prompt_calculator() -> str:
    return "You are a calculator assistant. Use the mcp-calculator tool to evaluate expressions."
 
@mcp.prompt(name="mcp-prompt-json-analyzer", description="Prompt template for JSON analysis use case.")
async def mcp_prompt_json_analyzer() -> str:
    return "You are a data analyst. Use the mcp-json-analyzer tool to analyze JSON numeric data."
 
@mcp.prompt(name="mcp-prompt-weather", description="Prompt template for weather lookup use case.")
async def mcp_prompt_weather() -> str:
    return "You are a weather assistant. Use the mcp-get-weather tool to get the forecast for a location."
 
@mcp.prompt(name="mcp-prompt-send-email", description="Prompt template for email dispatch use case.")
async def mcp_prompt_send_email() -> str:
    return "You are an automated mail agent. Use the mcp-send-email tool to send messages."
 
 
# --- Server Entrypoint ---
if __name__ == "__main__":
    import uvicorn
    print("\U0001F680 Launching MCP Data Utility App at http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
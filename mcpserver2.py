from typing import Union, List, Dict, Optional, Any
import statistics
import json
import logging
import requests
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP, Context
from snowflake.connector import SnowflakeConnection
from ReduceReuseRecycleGENAI.snowflake import snowflake_conn
from snowflake.core import Root
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger
from ReduceReuseRecycleGENAI.smtp import get_ser_conn

from mcp.server.fastmcp import Context, FastMCP
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Create a named server with the FastAPI app
mcp = FastMCP("DataFlyWheel App", app=app)

# --- Configurations ---
ENV = "preprod"
REGION_NAME = "us-east-1"
SENDER_EMAIL = 'AbhinavVarma.Lakamraju@elevancehealth.com'


# --- Categorized Prompt Library ---

PROMPT_LIBRARY = {
    "hedis": [
        {"name": "Explain BCS Measure", "prompt": "Explain the purpose of the BCS HEDIS measure."},
        {"name": "List 2024 HEDIS Measures", "prompt": "List all HEDIS measures for the year 2024."},
        {"name": "Age Criteria for CBP", "prompt": "What is the age criteria for the CBP measure?"}
    ],
    "contract": [
        {"name": "Summarize Contract H123", "prompt": "Summarize contract ID H123 for 2023."},
        {"name": "Compare Contracts H456 & H789", "prompt": "Compare contracts H456 and H789 on key metrics."}
    ]
}

# File to store dynamic prompts
PROMPTS_FILE = "dynamic_prompts.json"

# Function to load prompts from file
def load_prompts() -> Dict[str, List[dict]]:
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
    return {"hedis": [], "contract": []}

# Function to save prompts to file
def save_prompts(prompts: Dict[str, List[dict]]):
    try:
        with open(PROMPTS_FILE, 'w') as f:
            json.dump(prompts, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving prompts: {e}")

# Load dynamic prompts from file
DYNAMIC_PROMPTS = load_prompts()

class NewPrompt(BaseModel):
    name: str
    description: str
    prompt_text: str
    category: str

# Add new endpoints for dynamic prompt management
@app.get("/get_prompts")
async def get_prompts():
    """Get all prompts including dynamic ones"""
    return {
        "hedis": [
            {"name": "Explain BCS Measure", "prompt": "Explain the purpose of the BCS HEDIS measure."},
            {"name": "List 2024 HEDIS Measures", "prompt": "List all HEDIS measures for the year 2024."},
            {"name": "Age Criteria for CBP", "prompt": "What is the age criteria for the CBP HEDIS measure?"},
            *DYNAMIC_PROMPTS.get("hedis", [])
        ],
        "contract": [
            {"name": "Summarize Contract H123", "prompt": "Summarize contract ID H123 for 2023."},
            {"name": "Compare Contracts H456 & H789", "prompt": "Compare contracts H456 and H789 on key metrics."},
            *DYNAMIC_PROMPTS.get("contract", [])
        ]
    }

@app.post("/add_prompt")
async def add_prompt(new_prompt: NewPrompt):
    """Add a new prompt"""
    try:
        # Add to dynamic prompts
        if new_prompt.category not in DYNAMIC_PROMPTS:
            raise HTTPException(status_code=400, detail=f"Invalid category: {new_prompt.category}")
        
        # Create new prompt function
        async def new_prompt_func() -> str:
            print(f"\n📝 [{new_prompt.category.upper()}] {new_prompt.name} Prompt Called")
            return new_prompt.prompt_text

        # Register the prompt with MCP
        mcp.prompt(
            name=f"{new_prompt.category}.{new_prompt.name.lower().replace(' ', '-')}",
            description=new_prompt.description
        )(new_prompt_func)

        # Store in dynamic prompts
        DYNAMIC_PROMPTS[new_prompt.category].append({
            "name": new_prompt.name,
            "prompt": new_prompt.prompt_text
        })

        # Save to file
        save_prompts(DYNAMIC_PROMPTS)

        return {"status": "success", "message": "Prompt added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@dataclass
class AppContext:
    conn: SnowflakeConnection
    db: str
    schema: str
    host: str  


#@asynccontextmanager
#async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
#    """Manage application lifecycle with type-safe context"""
#    # Initialize on startup

#    try:
#        yield AppContext(conn=conn,db="DOC_AI_DB",schema="HEDIS_SCHEMA",host=HOST)
#    finally:
#        # Cleanup on shutdown
#        conn.close()


# Pass lifespan to server
#mcp = FastMCP("DataFlyWheel App", lifespan=app_lifespan)


#Stag name may need to be determined; requires code change
#Resources; Have access to resources required for the server; Cortex Search; Cortex stage schematic config; stage area should be fully qualified name
@mcp.resource(uri="schematiclayer://cortex_analyst/schematic_models/{stagename}/list", name="hedis_schematic_models", description="Hedis Schematic models")
async def get_schematic_model(stagename: str):
    """Cortex analyst schematic layer model, model is in yaml format"""
    #ctx = mcp.get_context()

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn = snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix=""
        )
    #conn = ctx.request_context.lifespan_context.conn
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'
    cursor = conn.cursor()
    snfw_model_list = cursor.execute("LIST @{db}.{schema}.{stagename}".format(db=db, schema=schema, stagename=stagename))

    return [stg_nm[0].split("/")[-1] for stg_nm in snfw_model_list if stg_nm[0].endswith('yaml')]
   
@mcp.resource(uri="search://cortex_search/search_obj/list", name="hedis_search", description="Hedis search indexes")
async def get_search_service():
    """Cortex search service"""

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn = snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix=""
        )
    #conn = ctx.request_context.lifespan_context.conn
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'
    cursor = conn.cursor()
    snfw_search_objs = cursor.execute("SHOW CORTEX SEARCH SERVICES IN SCHEMA {db}.{schema}".format(db=db, schema=schema))
    result = [search_obj[1] for search_obj in snfw_search_objs.fetchall()]
   
    return result

#Tools; corex Analyst; Cortex Search; Cortex Complete

@mcp.tool(
        name="DFWAnalyst",
        description="""
        Coneverts text to valid SQL which can be executed on HEDIS value sets and code sets.
       
        Example inputs:
           What are the codes in <some value> Value Set?

        Returns valid sql to retive data from underlying value sets and code sets.  

        Args:
               prompt (str):  text to be passed

        """
)
async def dfw_text2sql(prompt: str, ctx: Context) -> dict:
    """Tool to convert natural language text to snowflake sql for hedis system, text should be passed as 'prompt' input perameter"""

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn = snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix=""
        )

    #conn = ctx.request_context.lifespan_context.conn
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'    
    host = HOST
    stage_name = "hedis_stage_full"
    file_name = "hedis_semantic_model_complete.yaml"
    request_body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "semantic_model_file": f"@{db}.{schema}.{stage_name}/{file_name}",
    }

    token = conn.rest.token
    resp = requests.post(
        url=f"https://{host}/api/v2/cortex/analyst/message",
        json=request_body,
        headers={
            "Authorization": f'Snowflake Token="{token}"',
            "Content-Type": "application/json",
        },
    )
    return resp.json()

#Need to change the type of serch, implimented in the below code; Revisit
@mcp.tool(
        name="DFWSearch",
        description="""
        Searches HEDIS measure specification documents.

        Example inputs:
        What is the age criteria for BCS Measure?
        What is EED Measure in HEDIS?
        Describe COA Measure?
        What LOB is COA measure scoped under?

        Return result from HEDIS measure speficification documents.

        Args:
              query (str): text to be passed
       """
)
async def dfw_search(ctx: Context, query: str):
    """Tool to provide search againest HEDIS business documents for the year 2024, search string should be provided as 'query' perameter"""

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn = snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix=""
        )

    #conn = ctx.request_context.lifespan_context.conn
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'
    search_service = 'CS_HEDIS_FULL_2024'
    columns = ['chunk']
    limit = 2    

    root = Root(conn)
    search_service = root.databases[db].schemas[schema].cortex_search_services[search_service]
    response = search_service.search(
        query=query,
        columns=columns,
        limit=limit
    )
    return response.to_json()

@mcp.tool(
        name="calculator",
        description="""
        Evaluates a basic arithmetic expression.
        Supports: +, -, *, /, parentheses, decimals.

        Example inputs:
        3+4/5
        3.0/6*8

        Returns decimal result

        Args:
             expression (str): Arthamatic expression input
         
        """
)
def calculate(expression: str) -> str:
    """
    Evaluates a basic arithmetic expression.
    Supports: +, -, *, /, parentheses, decimals.
    """
    print(f" calculate() called with expression: {expression}", flush=True)
    try:
        allowed_chars = "0123456789+-*/(). "
        if any(char not in allowed_chars for char in expression):
            return " Invalid characters in expression."

        result = eval(expression)
        return f" Result: {result}"
    except Exception as e:
        print(" Error in calculate:", str(e), flush=True)
        return f" Error: {str(e)}"

@mcp.tool()
def get_weather(latitude: float, longitude: float) -> str:
    """
    Fetches current weather forecast for a given location using the NWS API.
   
    Args:
        latitude: Latitude of the location (e.g., 40.7128 for New York City)
        longitude: Longitude of the location (e.g., -74.0060 for New York City)
   
    Returns:
        Weather forecast information as a string
    """
    print(f" get_weather() called for coordinates: ({latitude}, {longitude})", flush=True)
    try:
        # Set headers for the API request
        headers = {
            "User-Agent": "MCP Weather Client (your-email@example.com)",
            "Accept": "application/geo+json"
        }
       
        # Step 1: Get the grid points for the provided coordinates
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        points_response = requests.get(points_url, headers=headers)
        points_response.raise_for_status()
        points_data = points_response.json()
       
        # Extract the forecast URL from the response
        forecast_url = points_data['properties']['forecast']
        location_name = f"{points_data['properties']['relativeLocation']['properties']['city']}, {points_data['properties']['relativeLocation']['properties']['state']}"
       
        # Step 2: Get the forecast using the URL from the previous response
        forecast_response = requests.get(forecast_url, headers=headers)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
       
        # Extract the current period's forecast
        current_period = forecast_data['properties']['periods'][0]
       
        # Format and return the weather information
        weather_info = (
            f" Weather for {location_name}:\n"
            f" - Period: {current_period['name']}\n"
            f" - Temperature: {current_period['temperature']}°{current_period['temperatureUnit']}\n"
            f" - Conditions: {current_period['shortForecast']}\n"
            f" - Wind: {current_period['windSpeed']} {current_period['windDirection']}\n"
            f" - Detailed Forecast: {current_period['detailedForecast']}"
        )
        return weather_info
       
    except requests.exceptions.RequestException as e:
        print(" Error in get_weather (request):", str(e), flush=True)
        return f" Error fetching weather data: {str(e)}"
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(" Error in get_weather (parsing):", str(e), flush=True)
        return f" Error parsing weather data: {str(e)}"

# --- Email Tool ---
class EmailRequest(BaseModel):
    subject: str
    body: str
    receivers: str

@mcp.tool(
    name="analyze",
    description="""
    Analyzes numeric data with statistical operations.

    Example inputs:
        Data: [1, 2, 3, 4, 5], Operation: "mean"
        Data: {"col1": [10, 20, 30], "col2": [5, 15, 25]}, Operation: "sum"

    Supported operations:
        "sum", "mean", "median", "min", "max", "average"

    Args:
        data (Union[List, Dict[str, List]]): Numeric data to analyze
        operation (str): Statistical operation to perform

    Returns:
        Dict: Result of statistical analysis with status
    """
)
async def analyze(data: Union[List, Dict[str, List]], operation: str) -> Dict:
    """Performs statistical analysis on numeric data"""
    logger.info(f"Analyzer called with operation: {operation}")
    try:
        operation = operation.lower()
        
        # Map 'average' to 'mean' since they are mathematically equivalent
        if operation == "average":
            operation = "mean"
            
        valid_ops = ["sum", "mean", "median", "min", "max", "average"]
        
        if operation not in valid_ops:
            return {"status": "error", "error": f"Invalid operation. Choose from: {', '.join(valid_ops)}"}

        def extract_numbers(raw):
            return [float(n) for n in raw if isinstance(n, (int, float)) or
                   (isinstance(n, str) and n.replace('.', '', 1).isdigit())]

        if isinstance(data, list):
            numbers = extract_numbers(data)
            if not numbers:
                return {"status": "error", "error": "No valid numeric values found in list."}

            result = {
                "sum": sum(numbers),
                "mean": statistics.mean(numbers),
                "median": statistics.median(numbers),
                "min": min(numbers),
                "max": max(numbers)
            }[operation]

            return {"status": "success", "result": result}

        elif isinstance(data, dict):
            result_dict = {}
            for key, values in data.items():
                if not isinstance(values, list):
                    continue

                numbers = extract_numbers(values)
                if numbers:
                    result_dict[key] = {
                        "sum": sum(numbers),
                        "mean": statistics.mean(numbers),
                        "median": statistics.median(numbers),
                        "min": min(numbers),
                        "max": max(numbers)
                    }[operation]

            if not result_dict:
                return {"status": "error", "error": "No valid numeric data in any columns."}

            return {"status": "success", "result": result_dict}

        return {"status": "error", "error": f"Invalid input type: {type(data).__name__}"}

    except Exception as e:
        logger.error(f"Error in analyzer: {str(e)}")
        return {"status": "error", "error": str(e)}

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

# --- MCP Prompts ---
# HEDIS Application Prompts
@mcp.prompt(name="hedis.explain-bcs", description="Explain the BCS HEDIS measure.")
async def explain_bcs() -> str:
    print("\n [HEDIS] BCS Prompt Called")
    return "Explain the purpose of the BCS HEDIS measure."

@mcp.prompt(name="hedis.list-2024", description="List HEDIS measures for 2024.")
async def list_hedis_2024() -> str:
    print("\n [HEDIS] 2024 List Prompt Called")
    return "List all HEDIS measures for the year 2024."

@mcp.prompt(name="hedis.cbp-age", description="Get age criteria for CBP measure.")
async def cbp_age_criteria() -> str:
    print("\n [HEDIS] CBP Age Criteria Prompt Called")
    return "What is the age criteria for the CBP HEDIS measure?"

# Contract Application Prompts
@mcp.prompt(name="contract.summarize-h123", description="Summarize contract ID H123.")
async def summarize_contract() -> str:
    print("\n [CONTRACT] H123 Summary Prompt Called")
    return "Summarize contract ID H123 for 2023."

@mcp.prompt(name="contract.compare", description="Compare contracts H456 and H789.")
async def compare_contracts() -> str:
    print("\n [CONTRACT] Comparison Prompt Called")
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


if __name__ == "__main__":
    mcp.run(transport="sse")
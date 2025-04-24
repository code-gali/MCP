from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from ReduceReuseRecycleGENAI.snowflake import snowflake_conn
from logging import Logger
import json
import logging
import mcp.types as types
 

import  snowflake.connector
import requests  
import os
from snowflake.connector import SnowflakeConnection
from snowflake.core import Root
from typing import Optional

from mcp.server.fastmcp import Context, FastMCP
logger=logging.getLogger(__name__)
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

@mcp.tool(name="ready-prompts", description="Return ready-made prompts by application category")
def get_ready_prompts(category: str) -> dict:
    category = category.lower()
    if category not in PROMPT_LIBRARY:
        return {"error": f"No prompts found for category '{category}'"}
    return {
        "category": category,
        "prompts": PROMPT_LIBRARY[category]
    }


# Create a named server
NWS_API_BASE = "https://api.weather.gov"
mcp = FastMCP("DataFlyWheel App")
PROMPTS = {
    "hedis-prompt": types.Prompt(
        name="hedis-prompt",
        description="Prompt to interact with hedis",
        arguments=[
            types.PromptArgument(
                name="query",
                description="Hedis query",
                required=True
            )
        ],
    ),
    "caleculator-promt": types.Prompt(
        name="caleculator-promt",
        description="Prompt to perform calculations",
        arguments=[],
    )
}

@dataclass
class AppContext:
    conn : SnowflakeConnection
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
@mcp.resource(uri="schematiclayer://cortex_analyst/schematic_models/{stagename}/list",name="hedis_schematic_models",description="Hedis Schematic models")
async def get_schematic_model(stagename: str):
    """Cortex analyst schematic layer model, model is in yaml format"""
    #ctx = mcp.get_context()

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn =  snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix =""
        )
    #conn = ctx.request_context.lifespan_context.conn 
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'
    cursor = conn.cursor()
    snfw_model_list = cursor.execute("LIST @{db}.{schema}.{stagename}".format(db=db,schema=schema,stagename=stagename)) 

    return [stg_nm[0].split("/")[-1] for stg_nm in  snfw_model_list if stg_nm[0].endswith('yaml')] 
    
@mcp.resource(uri="search://cortex_search/search_obj/list",name="hedis_search",description="Hedis search indexes")
async def get_search_service():
    """Cortex search service"""

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn =  snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix =""
        )
    #conn = ctx.request_context.lifespan_context.conn 
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'
    cursor = conn.cursor()
    snfw_search_objs = cursor.execute("SHOW CORTEX SEARCH SERVICES IN SCHEMA {db}.{schema}".format(db=db,schema=schema))
    result = [search_obj[1] for search_obj in  snfw_search_objs.fetchall()]
    
    return result

#Tools; corex Analyst; Cortex Search; Cortex Complete 

@mcp.tool(
        name="DFWAnalyst"
       ,description=""" 
        Coneverts text to valid SQL which can be executed on HEDIS value sets and code sets.
        
        Example inputs:
           What are the codes in <some value> Value Set?

        Returns valid sql to retive data from underlying value sets and code sets.  

        Args: 
               prompt (str):  text to be passed 

        """ 
)
async def dfw_text2sql(prompt:str,ctx: Context) -> dict:
    """Tool to convert natural language text to snowflake sql for hedis system, text should be passed as 'prompt' input perameter"""

    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn =  snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix =""
        )

    #conn = ctx.request_context.lifespan_context.conn 
    db = 'POC_SPC_SNOWPARK_DB'
    schema = 'HEDIS_SCHEMA'    
    host = HOST
    stage_name= "hedis_stage_full"
    file_name= "hedis_semantic_model_complete.yaml"
    request_body = {
        "messages":[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
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
        name="DFWSearch"
       ,description= """
        Searches HEDIS measure specification documents.

        Example inputs: 
        What is the age criteria for  BCS Measure ?
        What is EED Measure in HEDIS?
        Describe COA Measure?
        What LOB is COA measure scoped under?

        Return result from HEDIS measure speficification documents.

        Args: 
              query (str): text to be passed 
       """
)
async def dfw_search(ctx: Context,query: str):
    """Tool to provide search againest HEDIS business documents for the year 2024, search string should be provided as 'query' perameter"""


    HOST = "carelon-eda-preprod.privatelink.snowflakecomputing.com"
    conn =  snowflake_conn(
           logger,
           aplctn_cd="aedl",
           env="preprod",
           region_name="us-east-1",
           warehouse_size_suffix="",
           prefix =""
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
        
        limit = limit 
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
@mcp.prompt(name="hedis-prompt",description="Prompt to interact with hedis")
async def hedis_template_prompt()->str:
    return """You are expert in HEDIS system, HEDIS is a set of standardized measures that aim to improve healthcare quality by promoting accountability and transparency. You are provided with below tools: 1) DFWAnalyst - Generates SQL to retrive information for hedis codes and value sets. 2) DFWSearch -  Provides HEDIS measures, standards and criteria from latest specification document.You will respons with the results returned from right tool. {query}"""

@mcp.prompt(name="calculator-prompt",description="Prompt to perform calculations")
async def calculator_template_prompt()->str:
    return """you are expert in performing arithmetic operations,calculate the result using llm and verify the result using calculator tool"""
@mcp.prompt(name="weather-prompt",description="Prompt to report weather")
async def weather_template_prompt()->str:
    return """you are expert in reporting weather, you will report based on location like city ,place  from "https://api.weather.gov" """
 

if __name__ == "__main__":
    mcp.run(transport="sse")
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
# from ReduceReuseRecycleGENAI.snowflake import snowflake_conn
from logging import Logger
import json
import logging
import mcp.types as types

# import snowflake.connector
import requests  
import os

# from snowflake.connector import SnowflakeConnection
# from snowflake.core import Root
from typing import Optional

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)

# Create a named server
NWS_API_BASE = "https://api.weather.gov"
mcp = FastMCP("DataFlyWheel App")

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

#  Updated here: category is optional now
@mcp.tool(name="ready-prompts", description="Return ready-made prompts by application category")
def get_ready_prompts(category: Optional[str] = None) -> dict:
    if category:
        category = category.lower()
        if category not in PROMPT_LIBRARY:
            return {"error": f"No prompts found for category '{category}'"}
        return {
            "category": category,
            "prompts": PROMPT_LIBRARY[category]
        }
    else:
        return {
            "prompts": PROMPT_LIBRARY
        }

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

# @dataclass
# class AppContext:
#     conn : SnowflakeConnection
#     db: str 
#     schema: str
#     host: str  

# @asynccontextmanager
# async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
#     try:
#         yield AppContext(conn=conn,db="DOC_AI_DB",schema="HEDIS_SCHEMA",host=HOST)
#     finally:
#         conn.close()

# @mcp.resource(uri="schematiclayer://cortex_analyst/schematic_models/{stagename}/list",name="hedis_schematic_models",description="Hedis Schematic models")
# async def get_schematic_model(stagename: str):
#     ...

# @mcp.resource(uri="search://cortex_search/search_obj/list",name="hedis_search",description="Hedis search indexes")
# async def get_search_service():
#     ...

# @mcp.tool(name="DFWAnalyst", description="...")
# async def dfw_text2sql(prompt:str,ctx: Context) -> dict:
#     ...

# @mcp.tool(name="DFWSearch", description="...")
# async def dfw_search(ctx: Context,query: str):
#     ...

@mcp.tool(
    name="calculator",
    description="""
    Evaluates a basic arithmetic expression.
    Supports: +, -, *, /, parentheses, decimals.
    """
)
def calculate(expression: str) -> str:
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
    print(f" get_weather() called for coordinates: ({latitude}, {longitude})", flush=True)
    try:
        headers = {
            "User-Agent": "MCP Weather Client (your-email@example.com)",
            "Accept": "application/geo+json"
        }
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        points_response = requests.get(points_url, headers=headers)
        points_response.raise_for_status()
        points_data = points_response.json()
        forecast_url = points_data['properties']['forecast']
        location_name = f"{points_data['properties']['relativeLocation']['properties']['city']}, {points_data['properties']['relativeLocation']['properties']['state']}"
        forecast_response = requests.get(forecast_url, headers=headers)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        current_period = forecast_data['properties']['periods'][0]
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

@mcp.prompt(name="hedis-prompt", description="Prompt to interact with hedis")
async def hedis_template_prompt() -> str:
    return """You are expert in HEDIS system, HEDIS is a set of standardized measures that aim to improve healthcare quality by promoting accountability and transparency. You are provided with below tools: 1) DFWAnalyst - Generates SQL to retrieve information for hedis codes and value sets. 2) DFWSearch - Provides HEDIS measures, standards and criteria from latest specification document. You will respond with the results returned from right tool. {query}"""

@mcp.prompt(name="calculator-prompt", description="Prompt to perform calculations")
async def calculator_template_prompt() -> str:
    return """you are expert in performing arithmetic operations, calculate the result using llm and verify the result using calculator tool"""

@mcp.prompt(name="weather-prompt", description="Prompt to report weather")
async def weather_template_prompt() -> str:
    return """you are expert in reporting weather, you will report based on location like city, place from "https://api.weather.gov" """

if __name__ == "__main__":
    mcp.run(transport="sse")

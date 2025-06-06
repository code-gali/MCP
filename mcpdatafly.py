from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from urllib.parse import urlparse
from pathlib import Path
import json
from typing import List
from fastapi import HTTPException, status

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.prompts.base import Message

# Create a named server
mcp = FastMCP("DataFlyWheel App")

@mcp.resource("genaiplatform://{aplctn_cd}/frequent_questions/{user_context}")
async def frequent_questions(aplctn_cd: str, user_context: str) -> List[str]:
    resource_name = aplctn_cd + "_freq_questions.json"
    freq_questions = json.load(open(resource_name))
    aplcn_question = freq_questions.get(aplctn_cd)
    return [rec["prompt"] for rec in aplcn_question if rec["user_context"] == user_context]

@mcp.resource("genaiplatform://{aplctn_cd}/prompts")
async def prompt_list_by_app(aplctn_cd: str) -> List[dict]:
    """Return all prompts for a given application code"""
    logger.debug(f"GET all prompts for application: {aplctn_cd}")
    try:
        file_path = f"{aplctn_cd}_prompts.json"
        data = ensure_json_file(file_path, {aplctn_cd: []})
        prompts = data.get(aplctn_cd, [])
        return prompts  # returns full list of prompts (each with prompt_name, description, content)
    except Exception as e:
        logger.error(f"Error loading prompts for {aplctn_cd}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error loading prompts: {str(e)}"
        )


@mcp.tool(
        name="add-frequent-questions"
       ,description="""
        Tool to add frequent questions to MCP server

        Example inputs:
        {
           "uri"
        }

        Args:
               uri (str):  text to be passed
               questions (list):
               [
                 {
                   "user_context" (str): "User context for the prompt"
                   "prompt" (str): "prompt"

                 }
               ]
        """
)
async def add_frequent_questions(ctx: Context, uri: str, questions: list) -> list:
    #Parse and extract aplctn_cd and user_context (urllib)
    url_path = urlparse(uri)
    aplctn_cd = url_path.netloc
    user_context = Path(url_path.path).name
    file_data = {}
    file_name = aplctn_cd + "_freq_questions.json"
    if Path(file_name).exists():
        file_data  = json.load(open(file_name,'r'))
        file_data[aplctn_cd].extend(questions)
    else:
        file_data[aplctn_cd] =  questions

    index_dict = {
        user_context: set()
    }
    result = []
    #Remove duplicates
    for elm in file_data[aplctn_cd]:
        if elm["user_context"] == user_context and elm['prompt'] not in index_dict[user_context]:
            result.append(elm)
            index_dict[user_context].add(elm['prompt'])

    file_data[aplctn_cd] = result

    file = open(file_name,'w')
    file.write(json.dumps(file_data))

    return file_data[aplctn_cd]

@mcp.tool(
        name="add-prompts"
       ,description="""
        Tool to add prompts to MCP server

        Example inputs:
        {
           ""
        }

        Args:
               uri (str):  text to be passed
               prompts (dict):
                 {
                   "prompt_name" (str): "Unique name assigned to prompt for a application"
                   "description" (str): "Prompt description"
                   "content" (str): "Prompt content"

                 }
        """
)
async def add_prompts(ctx: Context, uri: str, prompt: dict) -> dict:
    #Parse and extract aplctn_cd and user_context (urllib)
    url_path = urlparse(uri)
    aplctn_cd = url_path.netloc
    prompt_name = Path(url_path.path).name
    
    def func1(query: str):
        return [
            {
                "role": "user",
                "content": prompt["content"] + f"\n  {query}"
            }
        ]
    ctx.fastmcp.add_prompt(
        Prompt.from_function(
            func1, name=prompt["prompt_name"], description=prompt["description"])
    )

    file_data = {}
    file_name = aplctn_cd + "_prompts.json"
    if Path(file_name).exists():
        file = open(file_name,'r')
        file_data  = json.load(file)
        file_data[aplctn_cd].append(prompt)
    else:
        file_data[aplctn_cd] =  [prompt]

    file = open(file_name,'w')
    file.write(json.dumps(file_data))

    return prompt

if __name__ == "__main__":
    mcp.run(transport="sse")

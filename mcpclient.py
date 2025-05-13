from mcp import (
    ClientSession, 
    StdioServerParameters,  
)
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["mcpserver.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write
        ) as session:
            # Initialize the connection
            await session.initialize()

            # List available resources
            resources = await session.list_resources()
            print(resources)
            # List available tools
            tools = await session.list_tools()
            print(tools)
            # Read a resource
            #content, mime_type = await session.read_resource("search://cortex_search/search_obj/list")

async def sse_run():
    async with sse_client(url='http://0.0.0.0:8000/sse') as sse_connection:
        async with ClientSession(
            *sse_connection
        ) as session:
            
            # Initialize the connection
            await session.initialize()
            
            # List available resources
            #resources = await session.list_resources()
            #print(resources)
            
            #resources = await session.list_resource_templates()
            #print(resources)

            #tools = await session.list_tools()
            #print(tools)
            
            #prompts = await session.list_prompts()
            #print(prompts)
            
            #Read a resource
            #content = await session.read_resource("genaiplatform://hedis/frequent_questions/Initialization")
            #print(content)
            #await session.call_tool(
            #    name="add-frequent-questions",
            #    arguments={
            #        "uri": "genaiplatform://hedis/frequent_questions/Initialization",
            #        "questions": [
            #            {
            #                "user_context": "Initialization",
            #                "prompt": "What is the age criteria for CBP Measure?"
            #            }
            #        ]
            #    }
            #)
            #content = await session.read_resource("genaiplatform://hedis/frequent_questions/Initialization")
            #print(content)

            #content = await session.read_resource("genaiplatform://hedis/prompts/Initialization")
            #print(content)
            content = await session.call_tool(
                name="add-prompts",
                arguments={
                    "uri": "genaiplatform://hedis/prompts/example-prompt",
                    "prompt": {
                            "prompt_name": "example-prompt",
                            "description": "Prompts to test the adding new prompts",
                            "content": "You are expert to answer HEDIS questions", 
                    }
                    
                }
            )
            print(content)
            content = await session.read_resource("genaiplatform://hedis/prompts/example-prompt")
            print(content)

            #await session.complete()
            
            #content = await session.read_resource("schematiclayer://cortex_analyst/schematic_models/hedis_stage_full/list")
            #print(content.contents)

            prompts = await session.list_prompts()
            print(prompts)

            prompt = await session.get_prompt(
                name="example-prompt",arguments={
                    "query": "what is your name"  
                }
            )
            print(prompt)

            
if __name__ == "__main__":
    import asyncio
    asyncio.run(sse_run())

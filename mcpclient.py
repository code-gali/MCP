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
    async with sse_client(url='http://localhost:8000/sse') as sse_connection:
        print(sse_connection)
        async with ClientSession(
            *sse_connection
        ) as session:
            
            print("Session Extablished")
            print(session)
            # Initialize the connection
            await session.initialize()
            

            print("Session Initialized")
            ready_prompts_response=await session.list_prompts()
            for category,prompts in ready_prompts_response["prompts"].items():
                print(f"\nCategory:{category}")
                for prompt_obj in prompts:
                    print("-",prompt_obj["name"],"=>",prompt_obj["prompt"])
            # List available resources
            resources = await session.list_resources()
            print(resources)
            

            # List available tools
            tools = await session.list_tools()
            print(tools)
            # Read a resource
            #content, mime_type = await session.read_resource("search://cortex_search/search_obj/list")

if __name__ == "__main__":
    import asyncio

    asyncio.run(sse_run())

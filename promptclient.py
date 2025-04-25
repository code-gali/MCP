from mcp.client.sse import sse_client
from mcp import ClientSession

async def run():
    async with sse_client("http://10.126.192.183:8001/sse") as sse_connection:
        async with ClientSession(*sse_connection) as session:
            await session.initialize()
            
            # Call ready-prompts tool
            ready_prompts_response = await session.call_tool(name="ready-prompts", arguments={})
            
            # Display all prompts grouped by application
            for category, prompts in ready_prompts_response["prompts"].items():
                print(f"\nCategory: {category}")
                for prompt_obj in prompts:
                    print(" -", prompt_obj["name"], "=>", prompt_obj["prompt"])

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())

import asyncio
from mcp.client.sse import SseClientTransport
from mcp import ClientSession

async def run():
    # Connect to your MCP Server using SSE
    async with SseClientTransport(url="http://10.126.192.183:8000/sse") as transport:
        # Open a session
        async with ClientSession(transport.read, transport.write) as session:
            await session.initialize()

            # Call the 'ready-prompts' tool correctly
            ready_prompts_response = await session.call_tool(
                name="ready-prompts",
                arguments={}  # No arguments needed
            )

            # Print all prompts grouped by application
            for category, prompts in ready_prompts_response["prompts"].items():
                print(f"\nCategory: {category}")
                for prompt_obj in prompts:
                    print(" -", prompt_obj["name"], "=>", prompt_obj["prompt"])

if __name__ == "__main__":
    asyncio.run(run())

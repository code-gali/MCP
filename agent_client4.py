from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from mcp.client.sse import sse_client
from mcp import (
    ClientSession, 
    StdioServerParameters,  
)
from dependencies import SnowFlakeConnector

from langchain_openai import ChatOpenAI
from llmobject_wrapper import ChatSnowflakeCortex
from snowflake.snowpark import Session

sf_conn = SnowFlakeConnector.get_conn(
            'aedl',
            '',
)

# LLM Model  
model = ChatSnowflakeCortex(
    model="llama3.1-70b-elevance",
    cortex_function="complete",
    session=Session.builder.configs({"connection": sf_conn}).getOrCreate()
)

async def run():

    ready_prompts_response = None

    # --- Step 1: Connect separately to get ready-prompts ---
    async with sse_client("http://10.126.192.183:8000/sse") as sse_connection:
        async with ClientSession(*sse_connection) as session:
            await session.initialize()
            ready_prompts_response = await session.invoke_tool(name="ready-prompts", arguments={})

    #  Step 2: Display all prompts (grouped by application)
    for category, prompts in ready_prompts_response["prompts"].items():
        print(f"\nCategory: {category}")
        for prompt_obj in prompts:
            print(" -", prompt_obj["name"], "=>", prompt_obj["prompt"])

    # --- Step 3: Connect as LangChain agent for normal tool usage ---
    async with MultiServerMCPClient(
        {
            "DataFlyWheelServer": {
                "url": "http://10.126.192.183:8001/sse",
                "transport": "sse",
            }
        }
    ) as client:
        
        agent = create_react_agent(model=model, tools=client.get_tools())

        #  Step 4: Pick one prompt (example: first prompt under "hedis")
        query = ""
        prompt = ready_prompts_response["prompts"]["hedis"][0]["prompt"] + "\n" + query

        # Send prompt to LLM agent
        response = await agent.ainvoke({"messages": prompt})
        print("\nResponse for query: ##### {query} #####".format(query=query))
        print("\nresult: {content}".format(content=list(response.values())[0][1].content))

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())

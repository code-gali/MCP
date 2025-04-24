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

#LLM Model  
model = ChatSnowflakeCortex(
    model="llama3.1-70b-elevance",
    cortex_function="complete",
    session=Session.builder.configs({"connection": sf_conn}).getOrCreate()
)

#hedis_prompt = """You are expert in HEDIS system, HEDIS is a set of standardized measures that aim to improve healthcare quality by promoting accountability and transparency. You are provided with below tools: 1) DFWAnalyst - Generates SQL to retrive information for hedis codes and value sets. 2) DFWSearch -  Provides HEDIS measures, standards and criteria from latest specification document.You will respons with the results returned from right tool. {query}"""

#general_prompt = """"""
#caleculator_promt =  """"""
async def run():

    async with MultiServerMCPClient(
        {
            "DataFlyWheelServer": {
                "url": "http://10.126.192.183:8000/sse",
                "transport": "sse",
            }
        }
    ) as client:
        agent = create_react_agent(model = model,tools= client.get_tools())

        #Prompt from server 
        #hedis_prompt_from_server = await client.get_prompt(server_name="DataFlyWheelServer",prompt_name="hedis-prompt",arguments= {})
        #Caleculator Prompt calculator-prompt
        #hedis_prompt_from_server = await client.get_prompt(server_name="DataFlyWheelServer",prompt_name="calculator-prompt",arguments= {})
        #hedis_prompt_from_server = await client.get_prompt(server_name="DataFlyWheelServer",prompt_name="weather-prompt",arguments= {})
        hedis_prompt_from_server = await client.invoke_tool(server_name="DataFlyWheelServer", tool_name="ready-prompts")


        #Query to test 
        #Case -1 empty Query  
        #query = ""
        
        #Case -2
        #query = "What are the different race startification for CBP HEDIS  Reporting"
        #query="What are the different HCPCS codes in the Colonoscopy Value set?"
        #query="Describe Care for Older Adults Measure"
        
        #Case -3 
        #query="What is the present weather in richmond"

        #Case -4 Perform caleculation and verify the result using tool
        #query = "(4+5)/2.0"

        #Case -5
        #query = "What are the different race startification for CBP HEDIS  Reporting and also calculate (4+5)/2.0"

        #promt = hedis_prompt_from_server[0].content.format(query=query)
        #promt = hedis_prompt_from_server[0].content + query
        query = ""
        promt = hedis_prompt_from_server["prompts"]["hedis"][0]["prompt"] + "\n" + query

        response = await agent.ainvoke({"messages": promt})
        print("\nResponse for query: ##### {query} #####".format(query=query))
        print("\nresult: {content}".format(content=list(response.values())[0][1].content))
        
 
 

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
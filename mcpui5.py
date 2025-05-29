import streamlit as st

# Page config must be the first Streamlit command
st.set_page_config(page_title="MCP DEMO")
st.title("MCP DEMO")

import asyncio
#import nest_asyncio
import json
import yaml
import os
from pathlib import Path

from mcp.client.sse import sse_client
from mcp import ClientSession

# from langchain_mcp_adapters.client import MultiServerMCPClient
# from langgraph.prebuilt import create_react_agent

# from dependencies import SnowFlakeConnector
# from llmobject_wrapper import ChatSnowflakeCortex
# from snowflake.snowpark import Session
from mcp.client.sse import sse_client
from mcp import ClientSession
# from langchain_mcp_adapters.client import MultiServerMCPClient

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import create_react_agent
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    st.warning("⚠️ langchain_mcp_adapters not available. Using mock responses.")

try:
    from dependencies import SnowFlakeConnector
    from llmobject_wrapper import ChatSnowflakeCortex
    from snowflake.snowpark import Session
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False
    st.warning("⚠️ Snowflake dependencies not available. Using mock responses.")

#nest_asyncio.apply()

server_url = st.sidebar.text_input("MCP Server URL", "http://localhost:8000/sse")
show_server_info = st.sidebar.checkbox("🛡 Show MCP Server Info", value=False)

# === MOCK LLM ===
def mock_llm_response(prompt_text: str) -> str:
    return f"🤖 Mock LLM Response to: '{prompt_text}'"

# === Server Info ===
# --- Show Server Information ---
if show_server_info:
    async def fetch_mcp_info():
        result = {"resources": [], "tools": [], "prompts": [], "yaml": [], "search": []}
        try:
            async with sse_client(url=server_url) as sse_connection:
                async with ClientSession(*sse_connection) as session:
                    await session.initialize()

                    # --- Resources ---
                    resources = await session.list_resources()
                    if hasattr(resources, 'resources'):
                        for r in resources.resources:
                            result["resources"].append({"name": r.name})
                    
                    # --- Tools (filtered) ---
                    tools = await session.list_tools()
                    hidden_tools = {"add-frequent-questions", "add-prompts", "suggested_top_prompts"}
                    if hasattr(tools, 'tools'):
                        for t in tools.tools:
                            if t.name not in hidden_tools:
                                result["tools"].append({
                                    "name": t.name,
                                      
                                })

                    # --- Prompts ---
                    prompts = await session.list_prompts()
                    if hasattr(prompts, 'prompts'):
                        for p in prompts.prompts:
                            args = []
                            if hasattr(p, 'arguments'):
                                for arg in p.arguments:
                                    args.append(f"{arg.name} ({'Required' if arg.required else 'Optional'}): {arg.description}")
                            result["prompts"].append({
                                "name": p.name,
                                "description": getattr(p, 'description', ''),
                                "args": args
                            })

                    # --- YAML Resources ---
                    try:
                        yaml_content = await session.read_resource("schematiclayer://cortex_analyst/schematic_models/hedis_stage_full/list")
                        if hasattr(yaml_content, 'contents'):
                            for item in yaml_content.contents:
                                if hasattr(item, 'text'):
                                    parsed = yaml.safe_load(item.text)
                                    result["yaml"].append(yaml.dump(parsed, sort_keys=False))
                    except Exception as e:
                        result["yaml"].append(f"YAML error: {e}")

                    # --- Search Objects ---
                    try:
                        content = await session.read_resource("search://cortex_search/search_obj/list")
                        if hasattr(content, 'contents'):
                            for item in content.contents:
                                if hasattr(item, 'text'):
                                    objs = json.loads(item.text)
                                    result["search"].extend(objs)
                    except Exception as e:
                        result["search"].append(f"Search error: {e}")

        except Exception as e:
            st.sidebar.error(f"❌ MCP Connection Error: {e}")
        return result

    mcp_data = asyncio.run(fetch_mcp_info())

   
    #--------------resource----------------------------
     # Display Resources
    with st.sidebar.expander("📦 Resources", expanded=False):
         for r in mcp_data["resources"]:

          # Match based on pattern inside the name

              if "cortex_search/search_obj/list" in r["name"]:

                   display_name = "Cortex Search"

              else:

                display_name = r["name"]

              st.markdown(f"**{display_name}**")
         # --- YAML Section ---
    with st.sidebar.expander("Schematic Layer", expanded=False):
        for y in mcp_data["yaml"]:
            st.code(y, language="yaml") 

    # --- Tools Section (Filtered) ---
    with st.sidebar.expander("🛠 Tools", expanded=False):
        for t in mcp_data["tools"]:
            st.markdown(f"**{t['name']}**")

 # Display Prompts
     # Display Prompts
    with st.sidebar.expander("🧐 Prompts", expanded=False):
       for p in mcp_data["prompts"]:
        st.markdown(f"**{p['name']}**")
else:
    # Re-enable Snowflake and LLM chatbot features
    # @st.cache_resource
    # def get_snowflake_connection():
    #     return SnowFlakeConnector.get_conn('aedl', '')

    # @st.cache_resource
    # def get_model():
    #     sf_conn = get_snowflake_connection()
    #     return ChatSnowflakeCortex(
    #         model="llama3.1-70b-elevance",
    #         cortex_function="complete",
    #         session=Session.builder.configs({"connection": sf_conn}).getOrCreate()
    #     )

    # === Add Tools to Sidebar ===
    with st.sidebar.expander("➕ Add Tools", expanded=False):
        # Add Custom Tool Dynamically
        st.subheader("�� Add Custom Tool")
        
        tool_name = st.text_input("Tool Name", key="tool_name")
        tool_desc = st.text_area("Tool Description", key="tool_desc")
        tool_code = st.text_area("Tool Function Code (must define a function)", height=200, key="tool_code")

        if st.button("Register Tool", key="register_tool_btn"):
            async def register_tool():
                try:
                    async with sse_client(url=server_url) as sse:
                        async with ClientSession(*sse) as session:
                            await session.initialize()
                            result = await session.call_tool(
                                name="add-dynamic-tool",
                                arguments={
                                    "name": tool_name,
                                    "description": tool_desc,
                                    "code": tool_code
                                }
                            )
                            st.success("✅ Tool registered!")
                            st.json(result.model_dump())
                            st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Failed to register tool: {e}")

            asyncio.run(register_tool())

        # Add Frequent Questions Tool
        st.subheader("❓ Add Frequent Question")
        app_code_q = st.text_input("Application Code", "hedis", key="app_code_question")
        user_context = st.text_input("User Context", "Initialization", key="user_context")
        question_prompt = st.text_input("Question", "What is the age criteria for CBP?", key="question_prompt")

        if st.button("Add Question", key="add_question_btn"):
            async def add_question():
                try:
                    # First check if file exists and create if needed
                    file_name = f"{app_code_q}_freq_questions.json"
                    if not Path(file_name).exists():
                        with open(file_name, 'w') as f:
                            json.dump({app_code_q: []}, f)

                    async with sse_client(url=server_url) as sse:
                        async with ClientSession(*sse) as session:
                            await session.initialize()
                            uri = f"genaiplatform://{app_code_q}/frequent_questions/{user_context}"
                            question_data = {
                                "user_context": user_context,
                                "prompt": question_prompt
                            }
                            result = await session.call_tool(
                                name="add-frequent-questions",
                                arguments={
                                    "uri": uri,
                                    "questions": [question_data]
                                }
                            )
                            st.success("✅ Question added successfully")
                            st.json(result.model_dump())
                            st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add question: {e}")

            asyncio.run(add_question())

        # Add Prompts Tool
        st.subheader("📝 Add Prompt")
        app_code_p = st.text_input("Application Code", "hedis", key="app_code_prompt")
        prompt_name = st.text_input("Prompt Name", "hedis-prompt", key="prompt_name")
        prompt_desc = st.text_input("Prompt Description", "Prompt to explain HEDIS measures", key="prompt_desc")
        prompt_content = st.text_area("Prompt Content", "You are expert in HEDIS...", key="prompt_content")

        if st.button("Add Prompt", key="add_prompt_btn"):
            async def add_prompt():
                try:
                    # First check if file exists and create if needed
                    file_name = f"{app_code_p}_prompts.json"
                    print(f"Debug UI - File name: {file_name}")
                    if not Path(file_name).exists():
                        print("Debug UI - Creating new file")
                        with open(file_name, 'w') as f:
                            json.dump({app_code_p: []}, f)

                    async with sse_client(url=server_url) as sse:
                        async with ClientSession(*sse) as session:
                            await session.initialize()
                            uri = f"genaiplatform://{app_code_p}/prompts/{prompt_name}"
                            prompt_data = {
                                "prompt_name": prompt_name,
                                "description": prompt_desc,
                                "content": prompt_content
                            }
                            print(f"Debug UI - Sending prompt data: {prompt_data}")
                            result = await session.call_tool(
                                name="add-prompts",
                                arguments={
                                    "uri": uri,
                                    "prompt": prompt_data
                                }
                            )
                            print(f"Debug UI - Server response: {result}")
                            st.success("✅ Prompt added successfully")
                            st.json(result.model_dump())
                            st.experimental_rerun()
                except Exception as e:
                    print(f"Debug UI - Error: {str(e)}")
                    st.error(f"❌ Failed to add prompt: {e}")

            asyncio.run(add_prompt())

    prompt_type = st.sidebar.radio("Select Prompt Type", ["Calculator", "HEDIS Expert", "Weather", "No Context"])
    prompt_map = {
        "Calculator": "caleculator-promt",
        "HEDIS Expert": "hedis-prompt",
        "Weather": "weather-prompt",
        "No Context": None
    }

    examples = {
        "Calculator": ["Caleculate the expression (4+5)/2.0", "Caleculate the math function sqrt(16) + 7", "Caleculate the expression 3^4 - 12"],
        "HEDIS Expert": [],
        "Weather": [
            "What is the present weather in Richmond?",
            "What's the weather forecast for Atlanta?",
            "Is it raining in New York City today?"
        ],
        "No Context": ["Who won the world cup in 2022?", "Summarize climate change impact on oceans"]
    }

    if prompt_type == "HEDIS Expert":
        try:
            async def fetch_hedis_examples():
                async with sse_client(url=server_url) as sse_connection:
                    async with ClientSession(*sse_connection) as session:
                        await session.initialize()
                        content = await session.read_resource("genaiplatform://hedis/frequent_questions/Initialization")
                        if hasattr(content, "contents"):
                            for item in content.contents:
                                if hasattr(item, "text"):
                                    examples["HEDIS Expert"].extend(json.loads(item.text))
    
            #examples["HEDIS Expert"] = asyncio.run(fetch_hedis_examples())
            asyncio.run(fetch_hedis_examples())
        except Exception as e:
            examples["HEDIS Expert"] = [f"⚠️ Failed to load examples: {e}"]

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    with st.sidebar.expander("Example Queries", expanded=True):
        for example in examples[prompt_type]:
            if st.button(example, key=example):
                st.session_state.query_input = example

    if query := st.chat_input("Type your query here...") or  "query_input" in st.session_state:

        if "query_input" in st.session_state:
            query = st.session_state.query_input
            del st.session_state.query_input
        
        with st.chat_message("user"):
            st.markdown(query,unsafe_allow_html=True)
        
        st.session_state.messages.append({"role": "user", "content": query})
    
        async def process_query(query_text):
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.text("Processing...")
                try:
                    # Use mock LLM response since LLM is not available
                    result = mock_llm_response(query_text)
                    # async with MultiServerMCPClient(
                    #     {"DataFlyWheelServer": {"url": server_url, "transport": "sse"}}
                    # ) as client:
                    #     model = get_model()
                    #     agent = create_react_agent(model=model, tools=client.get_tools())
                    #     prompt_name = prompt_map[prompt_type]
                    #     prompt_from_server = None 
                    #     if prompt_name == None:
                    #         prompt_from_server = query_text
                    #     else:  
                    #         prompt_from_server = await client.get_prompt(
                    #             server_name="DataFlyWheelServer",
                    #             prompt_name=prompt_name,
                    #             arguments={"query": query_text} 
                    #         )
                    #         if "{query}" in prompt_from_server[0].content:
                    #             formatted_prompt = prompt_from_server[0].content.format(query=query_text)
                    #         else:
                    #             formatted_prompt = prompt_from_server[0].content 
                    #     response = await agent.ainvoke({"messages": prompt_from_server})
                    #     result = list(response.values())[0][1].content
                    message_placeholder.text(result)
                    st.session_state.messages.append({"role": "assistant", "content": result})
                except Exception as e:
                    error_message = f"Error: {str(e)}"
                    message_placeholder.text(error_message)
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
            
            if query:
                asyncio.run(process_query(query))
            
            if st.sidebar.button("Clear Chat"):
                st.session_state.messages = []
                st.experimental_rerun()

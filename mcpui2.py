import streamlit as st
import asyncio
import nest_asyncio
import json
import yaml
import pandas as pd
from io import StringIO

from mcp.client.sse import sse_client
from mcp import ClientSession

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from dependencies import SnowFlakeConnector
from llmobject_wrapper import ChatSnowflakeCortex
from snowflake.snowpark import Session

# Page config
st.set_page_config(page_title="Healthcare AI Chat", page_icon="🏥")
st.title("Healthcare AI Chat")

nest_asyncio.apply()

# --- Sidebar Configuration ---
server_url = st.sidebar.text_input("MCP Server URL", "http://10.126.192.183:8000/sse")
show_server_info = st.sidebar.checkbox("🛡 Show MCP Server Info", value=False)

# --- Session Init ---
if 'prompts' not in st.session_state:
    st.session_state.prompts = {}
if 'selected_prompt' not in st.session_state:
    st.session_state.selected_prompt = None

# --- Show Server Information ---
if show_server_info:
    async def fetch_mcp_info():
        result = {"resources": [], "tools": [], "prompts": [], "yaml": []}
        try:
            async with sse_client(url=server_url) as sse_connection:
                async with ClientSession(*sse_connection) as session:
                    await session.initialize()
                    resources = await session.list_resources()
                    if hasattr(resources, 'resources'):
                        for r in resources.resources:
                            result["resources"].append({"name": r.name, "description": r.description})

                    tools = await session.list_tools()
                    if hasattr(tools, 'tools'):
                        for t in tools.tools:
                            result["tools"].append({"name": t.name, "description": getattr(t, 'description', 'No description')})

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

                    try:
                        yaml_content = await session.read_resource("schematiclayer://cortex_analyst/schematic_models/hedis_stage_full/list")
                        if hasattr(yaml_content, 'contents'):
                            for item in yaml_content.contents:
                                if hasattr(item, 'text'):
                                    parsed = yaml.safe_load(item.text)
                                    result["yaml"].append(yaml.dump(parsed, sort_keys=False))
                    except Exception as e:
                        result["yaml"].append(f"YAML error: {e}")

        except Exception as e:
            st.sidebar.error(f"❌ MCP Connection Error: {e}")
        return result

    mcp_data = asyncio.run(fetch_mcp_info())

    with st.sidebar.expander("📦 Resources", expanded=False):
        for r in mcp_data["resources"]:
            st.markdown(f"**{r['name']}**\n\n{r['description']}")

    with st.sidebar.expander("🛠 Tools", expanded=False):
        for t in mcp_data["tools"]:
            st.markdown(f"**{t['name']}**\n\n{t['description']}")

    with st.sidebar.expander("🧐 Prompts", expanded=False):
        for p in mcp_data["prompts"]:
            st.markdown(f"**{p['name']}**\n\n{p['description']}")
            if p["args"]:
                st.markdown("Arguments:")
                for a in p["args"]:
                    st.markdown(f"- {a}")

    with st.sidebar.expander("📄 YAML", expanded=False):
        for y in mcp_data["yaml"]:
            st.code(y, language="yaml")

else:
    @st.cache_resource
    def get_snowflake_connection():
        return SnowFlakeConnector.get_conn('aedl', '')

    @st.cache_resource
    def get_model():
        sf_conn = get_snowflake_connection()
        return ChatSnowflakeCortex(
            model="llama3.1-70b-elevance",
            cortex_function="complete",
            session=Session.builder.configs({"connection": sf_conn}).getOrCreate()
        )

    # --- PROMPTS UI ---
    st.sidebar.markdown("## 📌 Available Prompts")
    try:
        response = requests.get(f"{server_url.replace('/sse','')}/get_prompts")
        if response.status_code == 200:
            st.session_state.prompts = response.json()
    except Exception as e:
        st.sidebar.error(f"Prompt Fetch Error: {e}")

    for category, prompts in st.session_state.prompts.items():
        with st.sidebar.expander(f"📁 {category.upper()}"):
            for prompt in prompts:
                if st.button(prompt['name'], key=f"{category}-{prompt['name']}"):
                    st.session_state.selected_prompt = prompt

    st.sidebar.markdown("---")
    st.sidebar.markdown("## ➕ Add Prompt")
    new_prompt_text = st.sidebar.text_area("Enter your prompt")
    new_category = st.sidebar.selectbox("Select Category", list(st.session_state.prompts.keys()))
    if st.sidebar.button("Add Prompt"):
        name = new_prompt_text[:30] + "..." if len(new_prompt_text) > 30 else new_prompt_text
        new_prompt = {
            "name": name,
            "description": "User added prompt",
            "prompt_text": new_prompt_text,
            "category": new_category
        }
        try:
            response = requests.post(f"{server_url.replace('/sse','')}/add_prompt", json=new_prompt)
            if response.status_code == 200:
                st.success("Prompt added successfully!")
        except Exception as e:
            st.error(f"Failed to add prompt: {e}")

    # --- Chat with LLM ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    query = st.chat_input("Type your query here...")

    async def process_query(query_text):
        st.session_state.messages.append({"role": "user", "content": query_text})
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.text("Processing...")
            try:
                async with MultiServerMCPClient({"DataFlyWheelServer": {"url": server_url, "transport": "sse"}}) as client:
                    model = get_model()
                    agent = create_react_agent(model=model, tools=client.get_tools())
                    response = await agent.ainvoke({"messages": query_text})
                    result = list(response.values())[0][1].content
                    message_placeholder.text(result)
                    st.session_state.messages.append({"role": "assistant", "content": result})
            except Exception as e:
                message_placeholder.text(f"Error: {e}")
                st.session_state.messages.append({"role": "assistant", "content": str(e)})

    if query:
        asyncio.run(process_query(query))

    # --- Analyze Tool ---
    st.markdown("---")
    st.subheader("📊 Analyze Tool")
    uploaded_file = st.file_uploader("Upload a CSV or JSON file for analysis", type=["csv", "json"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_json(uploaded_file)
            st.dataframe(df)
            operation = st.selectbox("Select operation", ["sum", "mean", "median", "min", "max", "average"])
            if st.button("Run Analyze Tool"):
                payload = {
                    "data": df.to_dict(orient="list"),
                    "operation": operation
                }
                analyze_url = f"{server_url.replace('/sse','')}/tools/analyze"
                try:
                    result = requests.post(analyze_url, json=payload)
                    if result.status_code == 200:
                        st.success("Analysis Result")
                        st.json(result.json())
                    else:
                        st.error(f"Error: {result.status_code} {result.text}")
                except Exception as e:
                    st.error(f"Tool Error: {e}")
        except Exception as e:
            st.error(f"File processing error: {e}")

    if st.sidebar.button("Clear Chat"):
        st.session_state.messages = []
        st.experimental_rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("Healthcare AI Chat v1.0")
 

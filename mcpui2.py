import streamlit as st
import asyncio
import nest_asyncio
import json
from mcp.client.sse import sse_client
from mcp import ClientSession
import os

nest_asyncio.apply()

st.set_page_config(page_title="Healthcare Prompt Manager", page_icon="🧠", layout="wide")
st.title("🧠 Healthcare Prompt & Question Manager")

# Initialize session state for connection status
if 'connected' not in st.session_state:
    st.session_state.connected = False

# Set server URL
server_url = "http://localhost:8000/sse"
st.sidebar.text(f"Server URL: {server_url}")

# Test server connection
async def test_connection():
    try:
        async with sse_client(url=server_url) as sse:
            async with ClientSession(*sse) as session:
                await session.initialize()
                return True
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return False

# Test connection on startup
if not st.session_state.connected:
    connection_status = asyncio.run(test_connection())
    st.session_state.connected = connection_status
    if connection_status:
        st.sidebar.success("✅ Connected to server")
    else:
        st.sidebar.error("❌ Failed to connect to server")

# Function to load available items
def load_available_items():
    items = {"prompts": [], "questions": []}
    try:
        # Load prompts
        try:
            if os.path.exists("hedis_prompts.json"):
                with open("hedis_prompts.json", 'r') as f:
                    prompt_data = json.load(f)
                    if "hedis" in prompt_data:
                        items["prompts"] = prompt_data["hedis"]
                        st.sidebar.success(f"Found {len(items['prompts'])} prompts")
        except Exception as e:
            st.sidebar.error(f"Error loading prompts: {str(e)}")

        # Load frequent questions
        try:
            if os.path.exists("hedis_freq_questions.json"):
                with open("hedis_freq_questions.json", 'r') as f:
                    question_data = json.load(f)
                    if "hedis" in question_data:
                        items["questions"] = question_data["hedis"]
                        st.sidebar.success(f"Found {len(items['questions'])} questions")
        except Exception as e:
            st.sidebar.error(f"Error loading questions: {str(e)}")

    except Exception as e:
        st.sidebar.error(f"Error loading items: {str(e)}")
    return items

# --- Sidebar for Available Prompts and Questions ---
st.sidebar.header("📚 Available Items")

# Load available items
available_items = load_available_items()

# Display prompts in sidebar
if available_items["prompts"]:
    st.sidebar.subheader("📌 Available Prompts")
    for prompt in available_items["prompts"]:
        if st.sidebar.button(f"📝 {prompt['prompt_name']}", key=f"prompt_{prompt['prompt_name']}"):
            st.session_state.app_code_prompt = "hedis"
            st.session_state.prompt_name = prompt['prompt_name']
            st.session_state.prompt_desc = prompt['description']
            st.session_state.prompt_content = prompt['content']
            st.experimental_rerun()
else:
    st.sidebar.info("No prompts found. Add some prompts using the 'Add Prompt' tab.")

# Display questions in sidebar
if available_items["questions"]:
    st.sidebar.subheader("❓ Available Questions")
    for question in available_items["questions"]:
        if st.sidebar.button(f"💭 {question['prompt']}", key=f"question_{question['prompt']}"):
            st.session_state.app_code_question = "hedis"
            st.session_state.user_context = question['user_context']
            st.session_state.question_prompt = question['prompt']
            st.experimental_rerun()
else:
    st.sidebar.info("No questions found. Add some questions using the 'Add Question' tab.")

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["Add Prompt", "Add Question", "View Server Info"])

# --- Tab 1: Add Prompt ---
with tab1:
    st.header("📌 Add Prompt")
    app_code = st.text_input("Application Code", "hedis", key="app_code_prompt")
    prompt_name = st.text_input("Prompt Name", "hedis-prompt", key="prompt_name")
    prompt_desc = st.text_input("Description", "Prompt for HEDIS analysis", key="prompt_desc")
    prompt_content = st.text_area("Prompt Content", "You are an expert in HEDIS...", key="prompt_content")

    if st.button("Add Prompt"):
        if not st.session_state.connected:
            st.error("❌ Please connect to the server first")
        else:
            async def add_prompt():
                try:
                    async with sse_client(url=server_url) as sse:
                        async with ClientSession(*sse) as session:
                            await session.initialize()
                            uri = f"genaiplatform://{app_code}/prompts/{prompt_name}"
                            result = await session.call_tool(
                                name="add-prompts",
                                arguments={
                                    "uri": uri,
                                    "prompt": {
                                        "prompt_name": prompt_name,
                                        "description": prompt_desc,
                                        "content": prompt_content
                                    }
                                }
                            )
                            st.success("✅ Prompt added successfully")
                            st.json(result.model_dump())
                            # Reload available items after adding
                            st.session_state.available_items = load_available_items()
                            st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add prompt: {str(e)}")

            asyncio.run(add_prompt())

# --- Tab 2: Add Question ---
with tab2:
    st.header("❓ Add Frequent Question")
    app_code_q = st.text_input("Application Code", "hedis", key="app_code_question")
    user_context = st.text_input("User Context", "Initialization", key="user_context")
    question_prompt = st.text_input("Question", "What is the age criteria for CBP?", key="question_prompt")

    if st.button("Add Question"):
        if not st.session_state.connected:
            st.error("❌ Please connect to the server first")
        else:
            async def add_question():
                try:
                    async with sse_client(url=server_url) as sse:
                        async with ClientSession(*sse) as session:
                            await session.initialize()
                            uri = f"genaiplatform://{app_code_q}/frequent_questions/{user_context}"
                            result = await session.call_tool(
                                name="add-frequent-questions",
                                arguments={
                                    "uri": uri,
                                    "questions": [
                                        {"user_context": user_context, "prompt": question_prompt}
                                    ]
                                }
                            )
                            st.success("✅ Question added successfully")
                            st.json(result.model_dump())
                            # Reload available items after adding
                            st.session_state.available_items = load_available_items()
                            st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add question: {str(e)}")

            asyncio.run(add_question())

# --- Tab 3: Server Info ---
with tab3:
    st.header("📡 MCP Server Info")

    async def fetch_info():
        info = {"resources": [], "tools": [], "prompts": []}
        try:
            async with sse_client(url=server_url) as sse:
                async with ClientSession(*sse) as session:
                    await session.initialize()
                    
                    # List available resources
                    resources = await session.list_resources()
                    if hasattr(resources, 'resources'):
                        for r in resources.resources:
                            info["resources"].append({"name": r.name, "description": r.description})

                    # List available tools
                    tools = await session.list_tools()
                    if hasattr(tools, 'tools'):
                        for t in tools.tools:
                            info["tools"].append({"name": t.name, "description": getattr(t, 'description', 'No description')})

                    # List available prompts
                    prompts = await session.list_prompts()
                    if hasattr(prompts, 'prompts'):
                        for p in prompts.prompts:
                            info["prompts"].append({
                                "name": p.name,
                                "description": getattr(p, 'description', ''),
                                "content": getattr(p, 'content', '')
                            })

                    # Also try to read the prompts file directly
                    try:
                        if os.path.exists("hedis_prompts.json"):
                            with open("hedis_prompts.json", 'r') as f:
                                prompt_data = json.load(f)
                                if "hedis" in prompt_data:
                                    for p in prompt_data["hedis"]:
                                        info["prompts"].append({
                                            "name": p["prompt_name"],
                                            "description": p["description"],
                                            "content": p["content"]
                                        })
                    except Exception as e:
                        st.error(f"Error reading prompts file: {str(e)}")

        except Exception as e:
            st.error(f"Error fetching info: {str(e)}")
        return info

    server_info = asyncio.run(fetch_info())

    with st.expander("📦 Resources", expanded=False):
        for r in server_info["resources"]:
            st.markdown(f"**{r['name']}** - {r['description']}")

    with st.expander("🛠 Tools", expanded=False):
        for t in server_info["tools"]:
            st.markdown(f"**{t['name']}** - {t['description']}")

    with st.expander("🧠 Prompts", expanded=True):
        if not server_info["prompts"]:
            st.info("No prompts found. Add some prompts using the 'Add Prompt' tab.")
        else:
            for p in server_info["prompts"]:
                st.markdown(f"### {p['name']}")
                st.markdown(f"**Description:** {p['description']}")
                st.markdown(f"**Content:** {p['content']}")
                st.markdown("---")

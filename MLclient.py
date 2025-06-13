import asyncio
import os
from mcp.client.sse import sse_client
from mcp import ClientSession

async def predict():
    # Get input from user
    age = int(input("Enter age: "))
    whi = float(input("Enter WHI_Elevance score: "))
    plan = int(input("Enter insurance plan (0 or 1): "))
    smoker = int(input("Smoker? (1 = Yes, 0 = No): "))

    # Get server URL from environment variable or use default
    server_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8000')
    
    # Connect to MCP server
    async with sse_client(f"{server_url}/sse") as connection:
        async with ClientSession(*connection) as session:
            await session.initialize()

            result = await session.call_tool(
                name="predict-medical-cost",
                arguments={
                    "age": age,
                    "WHI_Elevance": whi,
                    "insurance_plan": plan,
                    "smoker": smoker
                }
            )
            # Extract just the predicted cost value
            predicted_cost = result.content[0].text if result.content else "No prediction available"
            print("\n✅ Predicted Medical Cost:", predicted_cost)

# Run the async function
asyncio.run(predict())

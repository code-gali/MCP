from mcp.server.fastmcp import FastMCP, Context
from fastapi import HTTPException
import pandas as pd
import joblib
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("ML App")

# Load model globally (only once at startup)
MODEL_PATH = "medical_cost_model.pkl"
model_data = None

try:
    if os.path.exists(MODEL_PATH):
        model_data = joblib.load(MODEL_PATH)
        logger.info("Model loaded successfully")
    else:
        logger.error(f"Model file not found at {MODEL_PATH}")
        raise RuntimeError("Model file not found. Train and save your model first.")
except Exception as e:
    logger.error(f"Error loading model: {str(e)}")
    raise RuntimeError(f"Failed to load model: {str(e)}")

@mcp.tool(
    name="predict-medical-cost",
    description="""
    Predict medical cost using trained ML model.

    Args:
        age (int): Age of the person
        WHI_Elevance (float): WHI_Elevance score
        insurance_plan (int): Plan type (e.g., 0 or 1)
        smoker (int): Smoker status (0 for No, 1 for Yes)

    Returns:
        str: Predicted medical cost in USD
    """
)
async def predict_medical_cost(ctx: Context, age: int, WHI_Elevance: float, insurance_plan: int, smoker: int) -> str:
    try:
        # Input validation
        if not isinstance(age, int) or age < 0:
            raise ValueError("Age must be a positive integer")
        if not isinstance(WHI_Elevance, (int, float)) or WHI_Elevance < 0:
            raise ValueError("WHI_Elevance must be a positive number")
        if not isinstance(insurance_plan, int) or insurance_plan not in [0, 1]:
            raise ValueError("Insurance plan must be 0 or 1")
        if not isinstance(smoker, int) or smoker not in [0, 1]:
            raise ValueError("Smoker status must be 0 or 1")

        # Create input DataFrame
        input_data = pd.DataFrame({
            'age': [age],
            'WHI_Elevance': [WHI_Elevance],
            'insurance_plan': [insurance_plan],
            'smoker': [smoker]
        })
        
        # Scale the input data
        input_scaled = model_data['scaler'].transform(input_data)
        
        # Make prediction
        prediction = model_data['model'].predict(input_scaled)[0]
        
        # Ensure non-negative prediction
        prediction = max(0, prediction)
        
        # Format and return result
        return f"${round(prediction, 2):,.2f}"
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

if __name__ == "__main__":
    try:
        logger.info("Starting MCP server...")
        mcp.run(transport="sse")
    except Exception as e:
        logger.error(f"Server startup failed: {str(e)}")
        raise


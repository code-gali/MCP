from fastapi import FastAPI
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
import statistics
from typing import Union, List, Dict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app and MCP server
app = FastAPI()
mcp = FastMCP("Calculator & Analyze Server", app=app)

# --- Calculator Tool ---
@mcp.tool(
    name="calculator",
    description="""
    Evaluates a basic arithmetic expression.
    Supports: +, -, *, /, parentheses, decimals.

    Example inputs:
    3+4/5
    3.0/6*8

    Returns decimal result

    Args:
         expression (str): Arithmetic expression input
    """
)
def calculate(expression: str) -> str:
    """
    Evaluates a basic arithmetic expression.
    Supports: +, -, *, /, parentheses, decimals.
    """
    logger.info(f"calculate() called with expression: {expression}")
    try:
        allowed_chars = "0123456789+-*/(). "
        if any(char not in allowed_chars for char in expression):
            return "Invalid characters in expression."
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        logger.error(f"Error in calculate: {str(e)}")
        return f"Error: {str(e)}"

# --- Analyze Tool ---
@mcp.tool(
    name="analyze",
    description="""
    Analyzes numeric data with statistical operations.

    Example inputs:
        Data: [1, 2, 3, 4, 5], Operation: "mean"
        Data: {"col1": [10, 20, 30], "col2": [5, 15, 25]}, Operation: "sum"

    Supported operations:
        "sum", "mean", "median", "min", "max", "average"

    Args:
        data (Union[List, Dict[str, List]]): Numeric data to analyze
        operation (str): Statistical operation to perform

    Returns:
        Dict: Result of statistical analysis with status
    """
)
async def analyze(data: Union[List, Dict[str, List]], operation: str) -> Dict:
    logger.info(f"Analyzer called with operation: {operation}")
    try:
        operation = operation.lower()
        if operation == "average":
            operation = "mean"
        valid_ops = ["sum", "mean", "median", "min", "max", "average"]
        if operation not in valid_ops:
            return {"status": "error", "error": f"Invalid operation. Choose from: {', '.join(valid_ops)}"}
        def extract_numbers(raw):
            return [float(n) for n in raw if isinstance(n, (int, float)) or (isinstance(n, str) and n.replace('.', '', 1).isdigit())]
        if isinstance(data, list):
            numbers = extract_numbers(data)
            if not numbers:
                return {"status": "error", "error": "No valid numeric values found in list."}
            result = {
                "sum": sum(numbers),
                "mean": statistics.mean(numbers),
                "median": statistics.median(numbers),
                "min": min(numbers),
                "max": max(numbers)
            }[operation]
            return {"status": "success", "result": result}
        elif isinstance(data, dict):
            result_dict = {}
            for key, values in data.items():
                if not isinstance(values, list):
                    continue
                numbers = extract_numbers(values)
                if numbers:
                    result_dict[key] = {
                        "sum": sum(numbers),
                        "mean": statistics.mean(numbers),
                        "median": statistics.median(numbers),
                        "min": min(numbers),
                        "max": max(numbers)
                    }[operation]
            if not result_dict:
                return {"status": "error", "error": "No valid numeric data in any columns."}
            return {"status": "success", "result": result_dict}
        return {"status": "error", "error": f"Invalid input type: {type(data).__name__}"}
    except Exception as e:
        logger.error(f"Error in analyzer: {str(e)}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse") 
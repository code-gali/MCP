import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import joblib
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def predict_medical_cost(age, whi_elevance, insurance_plan, smoker):
    """
    Predict medical cost using the trained model
    """
    try:
        # Load the saved model data
        model_data = joblib.load('medical_cost_model.pkl')
        
        # Create input data
        input_data = pd.DataFrame({
            'age': [age],
            'WHI_Elevance': [whi_elevance],
            'insurance_plan': [insurance_plan],
            'smoker': [smoker]
        })
        
        # Scale the input data using the saved scaler
        input_scaled = model_data['scaler'].transform(input_data)
        
        # Make prediction using the saved model
        # Convert input_scaled to 2D array if it's not already
        if input_scaled.ndim == 1:
            input_scaled = input_scaled.reshape(1, -1)
            
        prediction = model_data['model'].predict(input_scaled)[0]
        
        # Ensure non-negative prediction
        prediction = max(0, prediction)
        
        return round(prediction, 2)
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise

def train_model():
    try:
        # Load the existing dataset
        logger.info("Loading medical_costs.csv...")
        data = pd.read_csv('medical_costs.csv')
        logger.info(f"Dataset loaded successfully with {len(data)} records")
        
        # Validate data
        if (data['medical_cost'] < 0).any():
            logger.warning("Found negative medical costs in the dataset. These will be treated as errors.")
            data = data[data['medical_cost'] >= 0]
            logger.info(f"Dataset cleaned. Remaining records: {len(data)}")
        
        # Prepare features and target
        X = data[['age', 'WHI_Elevance', 'insurance_plan', 'smoker']]
        y = data['medical_cost']
        
        # Scale the features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        logger.info(f"Data split into {len(X_train)} training and {len(X_test)} test samples")
        
        # Create and train the model
        model = LinearRegression()
        model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = model.predict(X_test)
        
        # Ensure predictions are non-negative
        y_pred = np.maximum(y_pred, 0)
        
        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        # Print metrics in a more visible way
        print("\n" + "="*50)
        print("MODEL PERFORMANCE METRICS:")
        print("="*50)
        print(f"Mean Squared Error (MSE): {mse:,.2f}")
        print(f"R-squared (R²) Score: {r2:.4f}")
        print("="*50 + "\n")
        
        logger.info(f"Model trained successfully!")
        
        # Save the model and scaler
        model_data = {
            'model': model,
            'scaler': scaler,
            'feature_names': X.columns.tolist()
        }
        joblib.dump(model_data, 'medical_cost_model.pkl')
        logger.info("Model and scaler saved as 'medical_cost_model.pkl'")
        
        # Print model coefficients
        coefficients = pd.DataFrame({
            'Feature': X.columns,
            'Coefficient': model.coef_
        })
        print("\nModel Coefficients:")
        print(coefficients.to_string(index=False))
        
        # Print feature importance
        print("\nFeature Importance (Absolute Coefficients):")
        importance = pd.DataFrame({
            'Feature': X.columns,
            'Importance': np.abs(model.coef_)
        }).sort_values('Importance', ascending=False)
        print(importance.to_string(index=False))
        
        return model_data
        
    except FileNotFoundError:
        logger.error("medical_costs.csv file not found in the current directory")
        raise
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting model training...")
        model_data = train_model()
        logger.info("Training completed successfully!")
    except Exception as e:
        logger.error(f"Training failed: {str(e)}")
        raise

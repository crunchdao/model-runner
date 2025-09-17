# Example model for the generic Docker image
import typing
import json
import time
from datetime import datetime

class SimplePredictor:
    """Example predictor class for dynamic class loading"""
    
    def __init__(self, learning_rate: float = 0.01):
        self.learning_rate = learning_rate
        self.predictions = []
        
    def tick(self, data: dict):
        """Process incoming data"""
        self.predictions.append({
            'timestamp': datetime.now().isoformat(),
            'input': data,
            'processed_at': time.time()
        })
        
    def predict(self) -> dict:
        """Make a prediction"""
        if not self.predictions:
            return {'prediction': 0.0, 'confidence': 0.0}
            
        # Simple example: return the count of predictions
        return {
            'prediction': len(self.predictions),
            'confidence': min(1.0, len(self.predictions) * 0.1),
            'last_input': self.predictions[-1]['input'] if self.predictions else None
        }

# Generator-based inference function for streaming
def infer(payload_stream: typing.Iterator[dict]):
    """Example streaming inference function"""
    predictor = SimplePredictor(learning_rate=0.01)
    
    # Required initial yield
    yield
    
    for payload in payload_stream:
        # Process the payload
        predictor.tick(payload)
        
        # Yield prediction
        result = predictor.predict()
        yield result

def train():
    """Training function (placeholder)"""
    print("Training completed (placeholder)")
    pass
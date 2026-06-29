"""Test script for the API"""

import requests
import json
import numpy as np

API_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200

def test_train():
    """Test training endpoint"""
    print("Testing /train endpoint...")
    
    # Generate sample data
    n = 500
    data = []
    for i in range(n):
        daily = 50 * np.sin(2 * np.pi * i / 24) + 100
        noise = np.random.normal(0, 10)
        data.append(max(daily + noise, 0))
    
    payload = {
        "values": data,
        "sequence_length": 24
    }
    
    print(f"Sending {len(data)} data points...")
    response = requests.post(f"{API_URL}/train", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Training successful!")
        print(f"Metrics: {result['metrics']}")
        print(f"Train samples: {result['train_samples']}")
        print(f"Test samples: {result['test_samples']}\n")
        return True
    else:
        print(f"Error: {response.text}\n")
        return False

def test_forecast():
    """Test forecast endpoint"""
    print("Testing /forecast endpoint...")
    
    # Generate sequence
    sequence = [100 + 50 * np.sin(2 * np.pi * i / 24) for i in range(24)]
    
    payload = {
        "sequence": sequence,
        "steps": 24
    }
    
    response = requests.post(f"{API_URL}/forecast", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Forecast successful!")
        print(f"Generated {result['steps']} predictions")
        print(f"First 5 predictions: {result['forecast'][:5]}\n")
        return True
    else:
        print(f"Error: {response.text}\n")
        return False

if __name__ == "__main__":
    print("="*60)
    print("API Test Suite")
    print("="*60 + "\n")
    
    try:
        # Test health
        if not test_health():
            print("Health check failed. Is the server running?")
            exit(1)
        
        # Test training
        if not test_train():
            print("Training test failed")
            exit(1)
        
        # Test forecast
        if not test_forecast():
            print("Forecast test failed")
            exit(1)
        
        print("="*60)
        print("All tests passed! ✓")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to API server")
        print("Make sure the server is running: python backend/app.py")
    except Exception as e:
        print(f"ERROR: {str(e)}")

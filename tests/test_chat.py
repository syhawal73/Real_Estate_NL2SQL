import urllib.request
import json

def test_chat():
    url = "http://localhost:8000/chat"
    headers = {'Content-Type': 'application/json'}
    
    def post(data):
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    import uuid
    
    print("--- Test 1: Vague Query ---")
    data1 = post({"message": "Find me a property", "session_id": str(uuid.uuid4())})
    print("Intent:", data1.get("intent"))
    print("Clarification needed:", data1.get("clarification_needed"))
    print("Message:", data1.get("assistant_message"))
    print("\n")
    
    print("--- Test 2: Structured Query (Aggregation) ---")
    data2 = post({"message": "What is the average price of houses in Rome?", "session_id": str(uuid.uuid4())})
    print("Intent:", data2.get("intent"))
    print("Clarification needed:", data2.get("clarification_needed"))
    print("Message:", data2.get("assistant_message"))
    print("\n")
    
    print("--- Test 3: Context Switch ---")
    session3 = str(uuid.uuid4())
    data3 = post({"message": "Show apartments in Paris to rent", "session_id": session3})
    print("Intent:", data3.get("intent"))
    print("Clarification needed:", data3.get("clarification_needed"))
    print("Message:", data3.get("assistant_message"))
    print("\n")
    
    print("--- Test 4: City Switch ---")
    data4 = post({"message": "Switch to Berlin", "session_id": session3})
    print("Intent:", data4.get("intent"))
    print("Clarification needed:", data4.get("clarification_needed"))
    print("Message:", data4.get("assistant_message"))

if __name__ == "__main__":
    test_chat()

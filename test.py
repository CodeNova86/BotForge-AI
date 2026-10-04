import json
import os

# hi this is a test
def get_user_data():
    """Get user information from input."""
    print("Enter your information:")
    name = input("Name: ").strip()
    age = input("Age: ").strip()
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    
    return {
        "name": name,
        "age": age,
        "username": username,
        "email": email
    }

def save_user_data(user_data, filename="user_data.json"):
    """Save user data to a JSON file."""
    # Load existing data if file exists
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    
    # Append new user data
    data.append(user_data)
    
    # Save back to file
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"\nData saved to {filename}")

def main():
    user_data = get_user_data()
    save_user_data(user_data)
    
    # Display saved data
    print("\nSaved Information:")
    print(f"Name: {user_data['name']}")
    print(f"Age: {user_data['age']}")
    print(f"Username: {user_data['username']}")
    print(f"Email: {user_data['email']}")

if __name__ == "__main__":
    main()
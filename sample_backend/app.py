from fastapi import FastAPI

app = FastAPI(title="Demo Commerce API")


@app.get("/users")
def list_users():
    return [
        {
            "id": 1,
            "name": "Ash"
        }
    ]


@app.post("/users")
def create_user():
    return {
        "id": 2,
        "name": "New User"
    }


@app.get("/users/{user_id}")
def get_user(user_id: str):
    return {
        "id": user_id
    }


# HACKATHON DEMO:
# New API route added to simulate a backend change.
@app.post("/payments")
def create_payment():
    return {
        "paymentId": "p_123",
        "status": "success",
        "amount": 999,
        "currency": "INR",
        "transactionId": "TXN_2026_001"
    }

# HACKATHON DEMO:
# Another new API route added to simulate a second backend change.
@app.get("/products")
def list_products():
    return [
        {
            "id": 1,
            "name": "iQOO Phone"
        },
        {
            "id": 2,
            "name": "Laptop"
        }
    ]
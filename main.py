import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from database import db, create_document, get_documents
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CustomerOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    postcode: Optional[str] = None
    email: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


def _serialize_customer(doc: dict) -> CustomerOut:
    return CustomerOut(
        id=str(doc.get("_id")) if doc.get("_id") else "",
        first_name=doc.get("first_name", ""),
        last_name=doc.get("last_name", ""),
        phone=doc.get("phone"),
        address=doc.get("address"),
        postcode=doc.get("postcode"),
        email=doc.get("email"),
    )


@app.get("/api/customers/search", response_model=List[CustomerOut])
def search_customers(q: str = Query(..., min_length=3), limit: int = Query(25, ge=1, le=100)):
    """
    Search customers across first_name, last_name, phone, address, postcode, email.
    Requires at least 3 characters. Case-insensitive partial match.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    regex = {"$regex": q, "$options": "i"}
    filter_query = {
        "$or": [
            {"first_name": regex},
            {"last_name": regex},
            {"phone": regex},
            {"address": regex},
            {"postcode": regex},
            {"email": regex},
        ]
    }

    results = db["customer"].find(filter_query).limit(limit)
    return [_serialize_customer(doc) for doc in results]


@app.post("/api/customers/seed")
def seed_customers():
    """
    Quick seed endpoint to insert a handful of sample customers for testing the UI.
    Safe to call multiple times; it avoids duplicates by email when present.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    samples = [
        {"first_name": "Alice", "last_name": "Johnson", "phone": "555-123-4567", "address": "12 Rainbow Rd", "postcode": "AB12 3CD", "email": "alice@example.com"},
        {"first_name": "Bob", "last_name": "Smith", "phone": "555-987-1111", "address": "7 Sunset Blvd", "postcode": "XY98 7ZT", "email": "bob@example.com"},
        {"first_name": "Charlie", "last_name": "Nguyen", "phone": "+44 7700 900123", "address": "99 Market Street", "postcode": "M1 2AB", "email": "charlie@example.com"},
        {"first_name": "Diana", "last_name": "Lopez", "phone": "020 7946 0958", "address": "221B Baker Street", "postcode": "NW1 6XE", "email": "diana@example.com"},
        {"first_name": "Ethan", "last_name": "Patel", "phone": "07911 123456", "address": "5 Kings Way", "postcode": "SW1A 1AA", "email": "ethan@example.com"},
    ]

    inserted = 0
    for s in samples:
        existing = None
        if s.get("email"):
            existing = db["customer"].find_one({"email": s["email"]})
        if not existing:
            db["customer"].insert_one(s)
            inserted += 1

    return {"inserted": inserted, "total": db["customer"].count_documents({})}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

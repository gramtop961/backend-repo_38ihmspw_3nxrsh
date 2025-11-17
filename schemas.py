"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Class name lowercased = collection name (e.g., Page -> "page").
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime

class Page(BaseModel):
    """
    Crawled pages from mezzofy.com or related SME/SaaS content
    Collection: "page"
    """
    url: HttpUrl = Field(..., description="Canonical URL of the page")
    title: Optional[str] = Field(None, description="Page title")
    description: Optional[str] = Field(None, description="Meta description or summary")
    keywords_matched: List[str] = Field(default_factory=list, description="Matched filter keywords")
    snippet: Optional[str] = Field(None, description="Short content preview")
    source: Optional[str] = Field("mezzofy", description="Origin/source tag")
    image: Optional[str] = Field(None, description="OG image if available")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Example schemas kept for reference (can be removed if not needed)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True

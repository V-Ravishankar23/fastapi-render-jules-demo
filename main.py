from typing import Optional, Dict
from datetime import datetime

from fastapi import FastAPI, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import requests


# Pydantic Models
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Product name")
    description: Optional[str] = Field(None, max_length=500, description="Product description")
    price: float = Field(..., gt=0, description="Product price (must be greater than 0)")
    in_stock: bool = Field(default=True, description="Whether the product is in stock")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[float] = Field(None, gt=0)
    in_stock: Optional[bool] = None


class Product(ProductBase):
    id: int = Field(..., description="Unique product ID")
    created_at: str = Field(..., description="Creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Wireless Mouse",
                "description": "Ergonomic wireless mouse with USB receiver",
                "price": 29.99,
                "in_stock": True,
                "created_at": "2025-12-14T10:00:00"
            }
        }


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


# Initialize FastAPI with metadata
app = FastAPI(
    title="Product API Demo",
    description="A demo FastAPI application with CRUD operations for products",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database with seed data
INITIAL_PRODUCTS = [
    {
        "id": 1,
        "name": "Wireless Mouse",
        "description": "Ergonomic wireless mouse with USB receiver",
        "price": 29.99,
        "in_stock": True,
        "created_at": "2025-12-14T10:00:00"
    },
    {
        "id": 2,
        "name": "Mechanical Keyboard",
        "description": "RGB mechanical keyboard with blue switches",
        "price": 89.99,
        "in_stock": True,
        "created_at": "2025-12-14T10:00:00"
    },
    {
        "id": 3,
        "name": "USB-C Hub",
        "description": "7-in-1 USB-C hub with HDMI and SD card reader",
        "price": 45.50,
        "in_stock": False,
        "created_at": "2025-12-14T10:00:00"
    },
    {
        "id": 4,
        "name": "Laptop Stand",
        "description": "Adjustable aluminum laptop stand",
        "price": 39.99,
        "in_stock": True,
        "created_at": "2025-12-14T10:00:00"
    }
]

products_db: Dict[int, dict] = {product["id"]: product for product in INITIAL_PRODUCTS}
next_id = max(products_db.keys()) + 1 if products_db else 1


# Custom Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


# Health Check Endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns the current health status of the API"
)
async def health_check():
    """
    Health check endpoint for monitoring and deployment verification.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# Root Endpoint
@app.get(
    "/",
    tags=["Root"],
    summary="Welcome message",
    description="Returns a welcome message and API information"
)
async def root():
    """
    Welcome endpoint that provides basic API information.
    """
    return {
        "message": "Welcome to the Product API Demo",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# CRUD Endpoints
@app.get(
    "/api/v1/products",
    response_model=list[Product],
    tags=["Products"],
    summary="List all products",
    description="Retrieve a list of all products in the catalog"
)
async def list_products(
    in_stock: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size")
):
    """
    Get all products with optional filtering.

    - **in_stock**: Filter by stock availability
    - **min_price**: Filter by minimum price
    - **max_price**: Filter by maximum price
    """
    products = list(products_db.values())

    # Apply filters
    if in_stock is not None:
        products = [p for p in products if p["in_stock"] == in_stock]
    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]

    # Apply pagination
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_products = products[start_index:end_index]

    return paginated_products


@app.get(
    "/api/v1/products/{product_id}",
    response_model=Product,
    tags=["Products"],
    summary="Get a specific product",
    description="Retrieve details of a specific product by ID",
    responses={
        200: {"description": "Product found"},
        404: {"description": "Product not found"}
    }
)
async def get_product(product_id: int):
    """
    Get a single product by its ID.

    - **product_id**: The unique identifier of the product
    """
    if product_id not in products_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    return products_db[product_id]


@app.post(
    "/api/v1/products",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
    summary="Create a new product",
    description="Add a new product to the catalog"
)
async def create_product(product: ProductCreate):
    """
    Create a new product with the following information:

    - **name**: Product name (required)
    - **description**: Product description (optional)
    - **price**: Product price (required, must be > 0)
    - **in_stock**: Stock availability (default: true)
    """
    global next_id

    new_product = {
        "id": next_id,
        **product.model_dump(),
        "created_at": datetime.utcnow().isoformat()
    }
    products_db[next_id] = new_product
    next_id += 1

    return new_product


@app.put(
    "/api/v1/products/{product_id}",
    response_model=Product,
    tags=["Products"],
    summary="Update a product",
    description="Update an existing product's information",
    responses={
        200: {"description": "Product updated successfully"},
        404: {"description": "Product not found"}
    }
)
async def update_product(product_id: int, product_update: ProductUpdate):
    """
    Update an existing product. Only provided fields will be updated.

    - **product_id**: The unique identifier of the product to update
    """
    if product_id not in products_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )

    stored_product = products_db[product_id]
    update_data = product_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        stored_product[field] = value

    return stored_product


@app.delete(
    "/api/v1/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Products"],
    summary="Delete a product",
    description="Remove a product from the catalog",
    responses={
        204: {"description": "Product deleted successfully"},
        404: {"description": "Product not found"}
    }
)
async def delete_product(product_id: int):
    """
    Delete a product by its ID.

    - **product_id**: The unique identifier of the product to delete
    """
    if product_id not in products_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )

    del products_db[product_id]
    return None


@app.get(
    "/api/v1/github-status",
    tags=["External"],
    summary="Check GitHub API status",
    description="Fetches the current status of GitHub's API as an example of calling external services"
)
async def check_github_status():
    """
    Example endpoint that calls an external API (GitHub).

    This demonstrates integration with external services and validates
    that the API can make outbound HTTP requests.
    """
    try:
        response = requests.get("https://api.github.com/status", timeout=5)
        response.raise_for_status()
        return {
            "external_service": "GitHub API",
            "status": "reachable",
            "status_code": response.status_code,
            "checked_at": datetime.utcnow().isoformat()
        }
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to reach external service: {str(e)}"
        )
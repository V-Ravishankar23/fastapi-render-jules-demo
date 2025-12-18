import os
from typing import Optional, Dict, List
from datetime import datetime
import asyncio
import logging

from fastapi import FastAPI, HTTPException, status, Request, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    image_url: Optional[str] = Field(None, description="URL of the product image")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Wireless Mouse",
                "description": "Ergonomic wireless mouse with USB receiver",
                "price": 29.99,
                "in_stock": True,
                "created_at": "2025-12-14T10:00:00",
                "image_url": "/uploads/1.jpg"
            }
        }


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


class PaginatedProducts(BaseModel):
    total_items: int
    total_pages: int
    page: int
    page_size: int
    items: List[Product]


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


# Background task for periodic logging
async def periodic_logger():
    """
    Background task that logs information every 10 seconds.
    This demonstrates how logs appear in the Render UI.
    """
    counter = 0
    while True:
        counter += 1

        # Regular info logs (most common)
        logger.info(f"Periodic log message #{counter} - API is running smoothly")
        logger.info(f"Current product count: {len(products_db)} products in database")

        # Success patterns (every 2 cycles)
        if counter % 2 == 0:
            logger.info(f"✓ Health check passed - All systems operational")
            logger.info(f"SUCCESS: Database connection verified at {datetime.utcnow().isoformat()}")

        # Warning patterns (every 4 cycles)
        if counter % 4 == 0:
            logger.warning(f"WARNING: Memory usage at 75% - monitoring closely")
            logger.warning(f"WARN: Slow response time detected: 1.2s (threshold: 1.0s)")

        # Error patterns (every 7 cycles)
        if counter % 7 == 0:
            logger.error(f"ERROR: Failed to connect to external API - retrying...")
            logger.error(f"CRITICAL: Rate limit approaching - 95% of quota used")

        # Debug/trace patterns (every 3 cycles)
        if counter % 3 == 0:
            logger.debug(f"DEBUG: Cache hit ratio: 87% (1234 hits, 189 misses)")

        await asyncio.sleep(10)  # Log every 10 seconds


# Startup event to begin background logging
@app.on_event("startup")
async def startup_event():
    """
    Start the periodic logging task when the application starts.
    """
    logger.info("=" * 60)
    logger.info("FastAPI application starting up!")
    logger.info("Background logging task initiated")
    logger.info("Logs will appear every 10 seconds in Render UI")
    logger.info("=" * 60)
    asyncio.create_task(periodic_logger())


@app.on_event("shutdown")
async def shutdown_event():
    """
    Log when the application shuts down.
    """
    logger.info("FastAPI application shutting down...")


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
    response_model=PaginatedProducts,
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
    Get all products with optional filtering and pagination.
    - **in_stock**: Filter by stock availability
    - **min_price**: Filter by minimum price
    - **max_price**: Filter by maximum price
    - **page**: Page number for pagination
    - **page_size**: Number of items per page
    """
    products = list(products_db.values())
    # Apply filters
    if in_stock is not None:
        products = [p for p in products if p["in_stock"] == in_stock]
    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    # Paginate
    total_items = len(products)
    total_pages = (total_items + page_size - 1) // page_size
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_products = products[start_index:end_index]
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "items": paginated_products
    }


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


# Image Upload Endpoint
UPLOADS_DIR = "uploads"
THUMBNAIL_SIZE = (200, 200)

os.makedirs(UPLOADS_DIR, exist_ok=True)


def get_image_extension(content_type: str) -> Optional[str]:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(content_type)


@app.post(
    "/api/v1/products/{product_id}/image",
    response_model=Product,
    tags=["Products"],
    summary="Upload a product image",
    description="Upload an image for a specific product",
    responses={
        200: {"description": "Image uploaded successfully"},
        404: {"description": "Product not found"},
        400: {"description": "Invalid image format"},
        500: {"description": "Internal server error"}
    }
)
async def upload_product_image(product_id: int, file: UploadFile = File(...)):
    """
    Upload an image for a product.

    - **product_id**: The ID of the product to associate the image with
    - **file**: The image file to upload (PNG, JPG, WEBP)
    """
    if product_id not in products_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # Validate image format
    file_extension = get_image_extension(file.content_type)
    if not file_extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Only PNG, JPG, and WEBP are supported."
        )

    file_path = os.path.join(UPLOADS_DIR, f"{product_id}.{file_extension}")
    image_url = f"/{file_path}"

    try:
        # Save and process the image
        with Image.open(file.file) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            img.save(file_path)

        # Update product's image URL
        products_db[product_id]["image_url"] = image_url

    except IOError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing image file."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while uploading the file."
        )

    return products_db[product_id]

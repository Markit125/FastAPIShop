from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware


# FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development only)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Serve static files (e.g., CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as file:
        return file.read()

@app.get("/login", response_class=HTMLResponse)
async def read_login():
    with open("static/login.html", "r") as file:
        return file.read()

# Add a handler for the /shop endpoint
@app.get("/shop", response_class=HTMLResponse)
async def read_shop():
    with open("static/shop.html", "r") as file:
        return file.read()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db/shop")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")  # Use the environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Pydantic models for request and response
class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True






from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Product model
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    attributes = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationship with Category
    category = relationship("Category", back_populates="products")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    # Relationship with Products
    products = relationship("Product", back_populates="category")


from pydantic import BaseModel
from typing import Optional, Dict


# Pydantic model for creating a Category
class CategoryCreate(BaseModel):
    name: str

# Pydantic model for reading a Category
class Category(CategoryCreate):
    id: int

    class Config:
        from_attributes = True

# Pydantic model for Product
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category_id: Optional[int] = None
    attributes: Optional[Dict] = None

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

def seed_data(db: Session):
    print("Seeding database...")

    # Add sample categories
    
    categories = [
        Category(id=1, name="Electronics"),
        Category(id=2, name="Clothing"),
        Category(id=3, name="Books"),
    ]

    for category in categories:
        db.add(category)
        print(f"Added category: {category.name}")
    db.commit()

#     # Add sample products
#     products = [
#         Product(
#             name="Laptop",
#             description="A high-performance laptop",
#             price=1200.0,
#             stock=10,
#             category_id=1,
#             attributes={"brand": "Dell", "color": "Silver"},
#         ),
#         Product(
#             name="T-Shirt",
#             description="A comfortable cotton T-shirt",
#             price=20.0,
#             stock=50,
#             category_id=2,
#             attributes={"size": "M", "color": "Black"},
#         ),
#         Product(
#             name="Python for Beginners",
#             description="A book for learning Python",
#             price=30.0,
#             stock=20,
#             category_id=3,
#             attributes={"author": "John Doe", "language": "English"},
#         ),
#     ]
#     for product in products:
#         db.add(product)
#         print(f"Added product: {product.name}")
#     db.commit()

#     print("Database seeding complete.")

# Call the seed function
# @app.on_event("startup")
# def startup_event():
#     db = SessionLocal()
#     seed_data(db)
#     db.close()




# Routes
@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    print("Registering a new user...")  # Debugging: Log when registering a user
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = pwd_context.hash(user.password)
    db_user = User(email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/login")
def login_user(user: UserCreate, db: Session = Depends(get_db)):
    print("Logging in a user...")  # Debugging: Log when logging in a user
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not pwd_context.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Create a JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    
    # Return the token
    print("access token", access_token)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    print(f"Fetching user with ID: {user_id}")  # Debugging: Log when fetching a user
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Function to create an access token
def create_access_token(data: dict, expires_delta: timedelta):
    print("Creating an access token...")  # Debugging: Log when creating a token
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.get("/dashboard")
async def read_dashboard(token: str = Depends(oauth2_scheme)):
    print("Accessing the dashboard...")  # Debugging: Log when accessing the dashboard
    # does not reach
    # try:
    #     # Decode the JWT token
    #     print(f"Decoding token: {token}")  # Debugging: Log the token being decoded
    #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #     email: str = payload.get("sub")
    #     if email is None:
    #         raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    # except JWTError:
    #     print("JWT decoding failed!")  # Debugging: Log if JWT decoding fails
    #     raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    # print(f"Welcome to the dashboard, {email}!")  # Debugging: Log the welcome message
    # return {"message": f"Welcome to the dashboard, {email}!"}

@app.get("/debug")
def debug():
    return {"SECRET_KEY": os.getenv("SECRET_KEY")}



from fastapi import Depends, HTTPException

# Route to create a new product
@app.post("/products", response_model=Product)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

# Route to get all products
@app.get("/products", response_model=list[Product])
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products

# Route to get a single product by ID
@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Route to update a product
@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: int, product: ProductCreate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    for key, value in product.dict().items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product

# Route to delete a product
@app.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted"}

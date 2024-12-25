from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, List

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

@app.get("/shop", response_class=HTMLResponse)
async def read_shop():
    with open("static/shop.html", "r") as file:
        return file.read()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db/shop")

# Function to get a database connection
def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")  # Use the environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models for request and response
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    category_id: Optional[int] = None
    attributes: Optional[Dict] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    stock: int
    category_id: Optional[int]
    attributes: Optional[Dict]
    created_at: datetime

    class Config:
        from_attributes = True

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int

class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    quantity: int
    name: str
    price: float

    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    user_id: int
    total_amount: float
    status: str
    payment_id: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    status: str
    payment_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    price: float

    class Config:
        from_attributes = True

# Routes
@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/register")
    try:
        # Hash the password before saving it to the database
        hashed_password = pwd_context.hash(user.password)
        
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING id, name, email, role, created_at",
                (user.name, user.email, hashed_password, user.role),
            )
            new_user = cursor.fetchone()
            db.commit()
            return new_user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def login_user(user: UserLogin, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/login")
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        db_user = cursor.fetchone()
        if not db_user or not pwd_context.verify(user.password, db_user["password"]):
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": db_user["email"]}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/users")
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

@app.post("/categories", response_model=CategoryResponse)
def create_category(category: CategoryCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/categories create")
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO categories (name, parent_id) VALUES (%s, %s) RETURNING id, name, parent_id",
            (category.name, category.parent_id),
        )
        new_category = cursor.fetchone()
        db.commit()
        return new_category

@app.get("/categories", response_model=List[CategoryResponse])
def get_categories(db: psycopg2.extensions.connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()
        return categories

@app.post("/products", response_model=ProductResponse)
def create_product(product: ProductCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/products create")
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO products (name, description, price, stock, category_id, attributes, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, name, description, price, stock, category_id, attributes, created_at",
            (product.name, product.description, product.price, product.stock, product.category_id, product.attributes, datetime.utcnow()),
        )
        new_product = cursor.fetchone()
        db.commit()
        return new_product

@app.get("/products", response_model=List[ProductResponse])
def get_products(db: psycopg2.extensions.connection = Depends(get_db)):
    print("/products")
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        return products

# Route to get the user's cart
@app.get("/cart", response_model=List[CartItemResponse])
def get_cart(user_id: int, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/cart")
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT p.name, p.price, ci.id, ci.cart_id, ci.product_id, ci.quantity
            FROM cart_items ci
            JOIN cart c ON ci.cart_id = c.id
            JOIN products p ON ci.product_id = p.id
            WHERE c.user_id = %s
        """, (user_id,))
        cart_items = cursor.fetchall()
        print(cart_items)
        return cart_items  # Convert RealDictRow to dict

# Route to add an item to the user's cart
@app.post("/cart/items", response_model=CartItemResponse)
def add_cart_item(item: CartItemCreate, user_id: int, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/cart/items")
    with db.cursor() as cursor:
        # Get or create the user's cart
        cursor.execute("SELECT id FROM cart WHERE user_id = %s", (user_id,))
        cart = cursor.fetchone()
        if not cart:
            cursor.execute("INSERT INTO cart (user_id, created_at) VALUES (%s, NOW()) RETURNING id", (user_id,))
            cart = cursor.fetchone()
        
        # Add the item to the cart
        cursor.execute("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (%s, %s, %s)
            RETURNING id, cart_id, product_id, quantity
        """, (cart["id"], item.product_id, item.quantity))
        new_item = cursor.fetchone()
        
        # Fetch product name and price
        cursor.execute("SELECT name, price FROM products WHERE id = %s", (new_item["product_id"],))
        product = cursor.fetchone()
        
        # Combine the data
        new_item_with_product = {
            **new_item,
            "name": product["name"],
            "price": float(product["price"])
        }
        
        db.commit()
        return new_item_with_product

@app.post("/orders", response_model=OrderResponse)
def create_order(order: OrderCreate, db: psycopg2.extensions.connection = Depends(get_db)):
    print("/orders")
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO orders (user_id, total_amount, status, payment_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id, user_id, total_amount, status, payment_id, created_at",
            (order.user_id, order.total_amount, order.status, order.payment_id, datetime.utcnow()),
        )
        new_order = cursor.fetchone()
        db.commit()
        return new_order

# Function to create an access token
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@app.on_event("startup")
def startup_event():
    db = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        # Drop all tables
        drop_all_tables(db)

        # Recreate tables
        create_tables(db)

        # Insert sample data (optional)
        insert_sample_data(db)
    finally:
        db.close()


def drop_all_tables(db: psycopg2.extensions.connection):
    try:
        with db.cursor() as cursor:
            cursor.execute(
            """
                DROP TABLE IF EXISTS users CASCADE;
                DROP TABLE IF EXISTS categories CASCADE;
                DROP TABLE IF EXISTS products CASCADE;
                DROP TABLE IF EXISTS cart CASCADE;
                DROP TABLE IF EXISTS cart_items CASCADE;
                DROP TABLE IF EXISTS orders CASCADE;
                DROP TABLE IF EXISTS order_items CASCADE;
                DROP TABLE IF EXISTS user_logs CASCADE;
                DROP TABLE IF EXISTS recommendations CASCADE;
            """)
    except Exception as e:
        db.rollback()
        print(f"Error dropping tables: {e}")

def create_tables(db: psycopg2.extensions.connection):
    try:
        with db.cursor() as cursor:
            # Drop the users table if it exists
            cursor.execute("DROP TABLE IF EXISTS users CASCADE;")

            # Recreate the users table with the correct schema
            cursor.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL CHECK (role IN ('покупатель', 'администратор')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create other tables (categories, products, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,  -- Add UNIQUE constraint
                    parent_id INT REFERENCES categories(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,  -- Add UNIQUE constraint
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
                    stock INT NOT NULL CHECK (stock >= 0),
                    category_id INT REFERENCES categories(id) ON DELETE SET NULL,
                    attributes JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cart (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS cart_items (
                    id SERIAL PRIMARY KEY,
                    cart_id INT REFERENCES cart(id) ON DELETE CASCADE,
                    product_id INT REFERENCES products(id) ON DELETE CASCADE,
                    quantity INT NOT NULL CHECK (quantity > 0)
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount >= 0),
                    status VARCHAR(50) NOT NULL CHECK (status IN ('в обработке', 'отправлен', 'доставлен')),
                    payment_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
                    product_id INT REFERENCES products(id) ON DELETE CASCADE,
                    quantity INT NOT NULL CHECK (quantity > 0),
                    price DECIMAL(10, 2) NOT NULL CHECK (price >= 0)
                );

                CREATE TABLE IF NOT EXISTS user_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    action VARCHAR(255) NOT NULL,
                    product_id INT REFERENCES products(id) ON DELETE SET NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS recommendations (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    product_id INT REFERENCES products(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            db.commit()
            print("Tables created successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error creating tables: {e}")
def insert_sample_data(db: psycopg2.extensions.connection):
    print("Inserting sample data into categories and products...")
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING;
        """, ("Sample User", "s@s", pwd_context.hash("s"), "покупатель"))

        # Insert parent categories first
        cursor.execute("""
            INSERT INTO categories (name, parent_id)
            VALUES
                ('Электроника', NULL),
                ('Одежда', NULL),
                ('Обувь', NULL),
                ('Товары для дома', NULL),
                ('Товары для детей', NULL)
            ON CONFLICT (name) DO NOTHING;
        """)

        # Fetch the IDs of the parent categories
        cursor.execute("""
            SELECT id, name FROM categories WHERE name IN (
                'Электроника', 'Одежда', 'Обувь', 'Товары для дома', 'Товары для детей'
            );
        """)
        parent_categories = {row['name']: row['id'] for row in cursor.fetchall()}

        # Insert child categories with correct parent_id references
        cursor.execute("""
            INSERT INTO categories (name, parent_id)
            VALUES
                ('Компьютеры', %(electronics_id)s),
                ('Смартфоны', %(electronics_id)s),
                ('Телевизоры', %(electronics_id)s),
                ('Мужская одежда', %(clothing_id)s),
                ('Женская одежда', %(clothing_id)s),
                ('Спортивная обувь', %(shoes_id)s),
                ('Повседневная обувь', %(shoes_id)s),
                ('Мебель', %(home_goods_id)s),
                ('Декор', %(home_goods_id)s),
                ('Кухня', %(home_goods_id)s),
                ('Игрушки', %(kids_goods_id)s),
                ('Детская одежда', %(kids_goods_id)s)
            ON CONFLICT (name) DO NOTHING;
        """, {
            'electronics_id': parent_categories['Электроника'],
            'clothing_id': parent_categories['Одежда'],
            'shoes_id': parent_categories['Обувь'],
            'home_goods_id': parent_categories['Товары для дома'],
            'kids_goods_id': parent_categories['Товары для детей']
        })

        # Fetch the IDs of all categories (parent and child)
        cursor.execute("SELECT id, name FROM categories;")
        categories = {row['name']: row['id'] for row in cursor.fetchall()}

        # Insert products with correct category_id references
        cursor.execute("""
            INSERT INTO products (name, description, price, stock, category_id, attributes)
            VALUES
                ('Ноутбук', 'Мощный ноутбук для работы и игр', 50000.00, 10, %(computers_id)s, '{"color": "черный", "processor": "Intel i7", "ram": "16GB"}'),
                ('Смартфон', 'Современный смартфон с отличной камерой', 25000.00, 15, %(smartphones_id)s, '{"color": "белый", "camera": "12MP", "battery": "4000mAh"}'),
                ('Телевизор', 'Ультра HD телевизор с поддержкой Smart TV', 35000.00, 8, %(tvs_id)s, '{"size": "55 inch", "type": "LED", "resolution": "4K"}'),
                ('Футболка', 'Стильная мужская футболка', 1500.00, 50, %(mens_clothing_id)s, '{"size": "M", "color": "синий"}'),
                ('Платье', 'Элегантное платье для особых случаев', 3000.00, 30, %(womens_clothing_id)s, '{"size": "S", "color": "красный"}'),
                ('Кроссовки', 'Удобные кроссовки для спорта', 4000.00, 25, %(sports_shoes_id)s, '{"size": "42", "color": "черный"}'),
                ('Сандалии', 'Летние сандалии для отдыха', 2000.00, 40, %(casual_shoes_id)s, '{"size": "38", "color": "бежевый"}'),
                ('Кресло', 'Удобное кресло для офиса', 8000.00, 15, %(furniture_id)s, '{"color": "черный", "material": "кожа"}'),
                ('Кровать', 'Комфортная двуспальная кровать с матрасом', 25000.00, 20, %(furniture_id)s, '{"material": "дерево", "size": "King"}'),
                ('Игрушечный робот', 'Интерактивный робот для детей', 1500.00, 50, %(toys_id)s, '{"battery": "AA", "color": "красный"}'),
                ('Детская футболка', 'Яркая футболка для детей', 800.00, 60, %(kids_clothing_id)s, '{"size": "L", "color": "голубой"}'),
                ('aaaaa', 'sadf', 800.00, 60, %(kids_clothing_id)s, '{"size": "L", "color": "blue"}')
            ON CONFLICT (name) DO NOTHING;
        """, {
            'computers_id': categories['Компьютеры'],
            'smartphones_id': categories['Смартфоны'],
            'tvs_id': categories['Телевизоры'],
            'mens_clothing_id': categories['Мужская одежда'],
            'womens_clothing_id': categories['Женская одежда'],
            'sports_shoes_id': categories['Спортивная обувь'],
            'casual_shoes_id': categories['Повседневная обувь'],
            'furniture_id': categories['Мебель'],
            'toys_id': categories['Игрушки'],
            'kids_clothing_id': categories['Детская одежда']
        })

        db.commit()
        print("Sample data inserted successfully!")
    except Exception as e:
        print(f"Error inserting sample data: {e}")
    finally:
        cursor.close()
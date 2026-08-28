from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
import sqlite3
import json
from datetime import datetime

app = FastAPI(
    title="RetailSense - Inventory & Analytics Edge API",
    description="Local edge server API managing inventory and operational data stores.",
    version="1.0"
)

DB_FILE = "retailsense.db"

# --- DATABASE INITIALIZATION ---
def init_db():
    """Initializes the SQLite schema and seeds sample rows if empty."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # 1. Zones Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                zone_id TEXT PRIMARY KEY,
                zone_name TEXT NOT NULL,
                zone_type TEXT NOT NULL CHECK(zone_type IN ('entry', 'dwell', 'checkout', 'shelf')),
                roi_coordinates TEXT NOT NULL
            );
        """)
        
        # 2. Inventory Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                shelf_zone TEXT NOT NULL,
                expected_qty INTEGER NOT NULL DEFAULT 0,
                current_status TEXT NOT NULL DEFAULT 'in-stock' CHECK(current_status IN ('in-stock', 'low', 'out')),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (shelf_zone) REFERENCES zones(zone_id)
            );
        """)
        
        # 3. Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('entry', 'exit', 'dwell', 'queue_count', 'stock_alert', 'theft_flag')),
                zone_id TEXT NOT NULL,
                value INTEGER NOT NULL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
            );
        """)
        
        # Performance Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(current_status);")
        
        # Seed Mock Data if empty (Helper for hackathon testing)
        cursor.execute("SELECT COUNT(*) FROM zones")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO zones VALUES (?, ?, ?, ?)", [
                ("ZONE_ENT_01", "Main Entrance", "entry", "[[10,10],[100,10]]"),
                ("ZONE_SHF_A4", "Aisle 4 - Chips & Snacks", "shelf", "[[50,200],[250,200]]"),
                ("ZONE_CKO_01", "Counter 1 Queue", "checkout", "[[400,400],[600,450]]")
            ])
            cursor.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)", [
                ("SKU_10045", "Premium Potato Chips", "ZONE_SHF_A4", 25, "in-stock", datetime.now().isoformat()),
                ("SKU_10099", "Organic Corn Tortillas", "ZONE_SHF_A4", 2, "low", datetime.now().isoformat())
            ])
        conn.commit()

init_db()

# --- PYDANTIC SCHEMAS ---
class ZoneBase(BaseModel):
    zone_id: str = Field(..., example="ZONE_SHF_A4")
    zone_name: str = Field(..., example="Aisle 4 - Snacks")
    zone_type: str = Field(..., example="shelf")
    roi_coordinates: str = Field(..., example="[[50,200],[250,200]]")

class InventoryBase(BaseModel):
    product_id: str = Field(..., example="SKU_10045")
    product_name: str = Field(..., example="Premium Potato Chips")
    shelf_zone: str = Field(..., example="ZONE_SHF_A4")
    expected_qty: int = Field(..., ge=0, example=25)
    current_status: str = Field(..., example="in-stock")

class InventoryUpdate(BaseModel):
    product_name: Optional[str] = Field(None, example="Premium Potato Chips V2")
    shelf_zone: Optional[str] = Field(None, example="ZONE_SHF_A4")
    expected_qty: Optional[int] = Field(None, ge=0, example=20)
    current_status: Optional[str] = Field(None, example="low")

class EventCreate(BaseModel):
    type: str = Field(..., example="stock_alert")
    zone_id: str = Field(..., example="ZONE_SHF_A4")
    value: int = Field(..., example=1)

# --- INVENTORY CRUD ENDPOINTS ---

@app.post("/api/inventory", status_code=status.HTTP_201_CREATED, response_model=InventoryBase, tags=["Inventory"])
def create_inventory_item(item: InventoryBase):
    """Adds a new product catalog item to the local database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO inventory (product_id, product_name, shelf_zone, expected_qty, current_status, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
                (item.product_id, item.product_name, item.shelf_zone, item.expected_qty, item.current_status, datetime.now().isoformat())
            )
            conn.commit()
        return item
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Product ID already exists or Shelf Zone is invalid.")

@app.get("/api/inventory", response_model=List[InventoryBase], tags=["Inventory"])
def get_all_inventory():
    """Retrieves all active items in the inventory database."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, product_name, shelf_zone, expected_qty, current_status FROM inventory")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.get("/api/inventory/{product_id}", response_model=InventoryBase, tags=["Inventory"])
def get_inventory_item(product_id: str):
    """Fetches details for a single specific SKU code."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, product_name, shelf_zone, expected_qty, current_status FROM inventory WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product item not found.")
        return dict(row)

@app.put("/api/inventory/{product_id}", response_model=InventoryBase, tags=["Inventory"])
def update_inventory_item(product_id: str, item_patch: InventoryUpdate):
    """Modifies product counts or operational statuses dynamically."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ensure item exists
        cursor.execute("SELECT * FROM inventory WHERE product_id = ?", (product_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Product item not found.")
        
        # Construct dynamic patching query
        update_data = item_patch.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update.")
        
        update_data["last_updated"] = datetime.now().isoformat()
        query_fields = ", ".join([f"{key} = ?" for key in update_data.keys()])
        values = list(update_data.values()) + [product_id]
        
        try:
            cursor.execute(f"UPDATE inventory SET {query_fields} WHERE product_id = ?", values)
            conn.commit()
            
            cursor.execute("SELECT product_id, product_name, shelf_zone, expected_qty, current_status FROM inventory WHERE product_id = ?", (product_id,))
            return dict(cursor.fetchone())
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Constraint violation during update. Verify shelf_zone exists.")

@app.delete("/api/inventory/{product_id}", tags=["Inventory"])
def delete_inventory_item(product_id: str):
    """Removes a product entirely from tracking mappings."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE product_id = ?", (product_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product item not found.")
        conn.commit()
    return {"message": f"Successfully deleted item {product_id}."}

# --- EDGE AI PIPELINE ENDPOINTS ---

@app.post("/api/events", status_code=status.HTTP_201_CREATED, tags=["AI Processing Pipeline"])
def log_operational_event(event: EventCreate):
    """Allows the CV tracking pipeline to drop state indicators down to local storage."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (type, zone_id, value, timestamp) VALUES (?, ?, ?, ?)",
                (event.type, event.zone_id, event.value, datetime.now().isoformat())
            )
            conn.commit()
        return {"status": "event_persisted", "type": event.type}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Failed to log event. Validate that your zone_id matches an existing tracking zone.")

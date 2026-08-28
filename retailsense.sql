PRAGMA foreign_keys = ON;

-- 1. ZONES


CREATE TABLE IF NOT EXISTS zones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_name TEXT NOT NULL UNIQUE,

    zone_type TEXT NOT NULL
        CHECK (
            zone_type IN (
                'entry',
                'exit',
                'dwell',
                'checkout',
                'shelf'
            )
        ),

    roi_coordinates TEXT NOT NULL,

    threshold_value REAL DEFAULT NULL,

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0,1)),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 2. PRODUCTS


CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,

    sku TEXT NOT NULL UNIQUE,

    product_name TEXT NOT NULL,

    category TEXT,

    description TEXT,

    price REAL DEFAULT 0
        CHECK (price >= 0),

    reorder_level INTEGER NOT NULL DEFAULT 5
        CHECK (reorder_level >= 0),

    expected_shelf_quantity INTEGER NOT NULL DEFAULT 0
        CHECK (expected_shelf_quantity >= 0),

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0,1)),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 3. INVENTORY

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,

    product_id INTEGER NOT NULL,

    shelf_zone_id INTEGER NOT NULL,

    expected_qty INTEGER NOT NULL DEFAULT 0
        CHECK (expected_qty >= 0),

    current_qty INTEGER NOT NULL DEFAULT 0
        CHECK (current_qty >= 0),

    current_status TEXT NOT NULL DEFAULT 'in_stock'
        CHECK (
            current_status IN (
                'in_stock',
                'low',
                'out'
            )
        ),

    last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE CASCADE,

    FOREIGN KEY (shelf_zone_id)
        REFERENCES zones(zone_id)
        ON DELETE RESTRICT,

    UNIQUE(product_id, shelf_zone_id)
);



-- 4. STOCK MOVEMENTS


CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,

    product_id INTEGER NOT NULL,

    movement_type TEXT NOT NULL
        CHECK (
            movement_type IN (
                'restock',
                'sale',
                'manual_adjustment',
                'shelf_removal',
                'unknown'
            )
        ),

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    previous_qty INTEGER NOT NULL
        CHECK (previous_qty >= 0),

    new_qty INTEGER NOT NULL
        CHECK (new_qty >= 0),

    reference_id TEXT,

    source TEXT NOT NULL DEFAULT 'system',

    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE CASCADE
);



-- 5. SHELF OBSERVATIONS


CREATE TABLE IF NOT EXISTS shelf_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,

    product_id INTEGER NOT NULL,

    zone_id INTEGER NOT NULL,

    detected_qty INTEGER NOT NULL
        CHECK (detected_qty >= 0),

    confidence REAL DEFAULT NULL
        CHECK (
            confidence IS NULL
            OR (confidence >= 0 AND confidence <= 1)
        ),

    observation_type TEXT NOT NULL DEFAULT 'vision',

    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE CASCADE,

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id)
        ON DELETE CASCADE
);



-- 6. SALES / POS EVENTS
-- Used by the anti-theft heuristic even if a real POS
-- integration is not present yet.


CREATE TABLE IF NOT EXISTS sales_events (
    sale_event_id INTEGER PRIMARY KEY AUTOINCREMENT,

    product_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL
        CHECK (quantity > 0),

    transaction_reference TEXT,

    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE CASCADE
);



-- 7. SYSTEM EVENTS


CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,

    event_type TEXT NOT NULL
        CHECK (
            event_type IN (
                'entry',
                'exit',
                'dwell',
                'queue_count',
                'stock_alert',
                'theft_flag',
                'restock',
                'inventory_update'
            )
        ),

    zone_id INTEGER,

    product_id INTEGER,

    value REAL,

    metadata TEXT,

    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (zone_id)
        REFERENCES zones(zone_id)
        ON DELETE SET NULL,

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
        ON DELETE SET NULL
);


-- 8. THRESHOLDS

CREATE TABLE IF NOT EXISTS thresholds (
    threshold_id INTEGER PRIMARY KEY AUTOINCREMENT,

    threshold_name TEXT NOT NULL UNIQUE,

    threshold_type TEXT NOT NULL
        CHECK (
            threshold_type IN (
                'low_stock',
                'queue_warning',
                'queue_critical',
                'dwell',
                'theft_window'
            )
        ),

    threshold_value REAL NOT NULL,

    unit TEXT,

    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0,1)),

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);



-- 9. INDEXES


CREATE INDEX IF NOT EXISTS idx_inventory_product
ON inventory(product_id);

CREATE INDEX IF NOT EXISTS idx_inventory_status
ON inventory(current_status);

CREATE INDEX IF NOT EXISTS idx_inventory_zone
ON inventory(shelf_zone_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product
ON stock_movements(product_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_timestamp
ON stock_movements(timestamp);

CREATE INDEX IF NOT EXISTS idx_shelf_observations_product
ON shelf_observations(product_id);

CREATE INDEX IF NOT EXISTS idx_shelf_observations_timestamp
ON shelf_observations(timestamp);

CREATE INDEX IF NOT EXISTS idx_events_type
ON events(event_type);

CREATE INDEX IF NOT EXISTS idx_events_timestamp
ON events(timestamp);

CREATE INDEX IF NOT EXISTS idx_events_product
ON events(product_id);



-- 10. DEFAULT THRESHOLDS


INSERT OR IGNORE INTO thresholds
(
    threshold_name,
    threshold_type,
    threshold_value,
    unit
)
VALUES
(
    'Default Low Stock',
    'low_stock',
    5,
    'units'
),

(
    'Queue Warning',
    'queue_warning',
    5,
    'people'
),

(
    'Queue Critical',
    'queue_critical',
    10,
    'people'
),

(
    'Theft Review Window',
    'theft_window',
    60,
    'seconds'
);
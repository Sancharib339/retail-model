-- 1. ZONES TABLE
-- Stores the coordinates for camera tracking regions (shelves, entryways, checkout lines)
CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    zone_type TEXT NOT NULL CHECK(zone_type IN ('entry', 'dwell', 'checkout', 'shelf')),
    roi_coordinates TEXT NOT NULL -- Saved as a JSON string of polygon coordinates (e.g., "[[x1,y1],[x2,y2],...]")
);

-- 2. INVENTORY TABLE
-- Tracks standard product items, where they sit, and their current quantities
CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    shelf_zone TEXT NOT NULL,
    expected_qty INTEGER NOT NULL DEFAULT 0,
    current_status TEXT NOT NULL DEFAULT 'in-stock' CHECK(current_status IN ('in-stock', 'low', 'out')),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shelf_zone) REFERENCES zones(zone_id)
);

-- 3. EVENTS TABLE
-- Logs every AI-generated event or operational change over time for trend forecasting
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('entry', 'exit', 'dwell', 'queue_count', 'stock_alert', 'theft_flag')),
    zone_id TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0, -- Keeps numeric values like live headcounts or stock tallies
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

-- CREATE INDEXES FOR FAST LOCAL LOOKUPS (Critical for edge hardware performance)
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(current_status);

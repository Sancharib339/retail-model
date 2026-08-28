-- Zones

INSERT INTO zones
(zone_name, zone_type, roi_coordinates)
VALUES
('Entrance', 'entry', '[[50,100],[300,100],[300,500],[50,500]]'),

('Checkout', 'checkout', '[[600,100],[900,100],[900,500],[600,500]]'),

('Shelf A1', 'shelf', '[[100,600],[350,600],[350,800],[100,800]]'),

('Shelf A2', 'shelf', '[[400,600],[650,600],[650,800],[400,800]]');


-- Products

INSERT INTO products
(
    sku,
    product_name,
    category,
    price,
    reorder_level,
    expected_shelf_quantity
)
VALUES
(
    'SKU001',
    'Coca Cola 500ml',
    'Beverages',
    40,
    5,
    10
),

(
    'SKU002',
    'Parle-G Biscuit',
    'Food',
    10,
    8,
    20
),

(
    'SKU003',
    'Dove Soap',
    'Personal Care',
    55,
    4,
    8
);


-- Inventory

INSERT INTO inventory
(
    product_id,
    shelf_zone_id,
    expected_qty,
    current_qty,
    current_status
)
VALUES
(1, 3, 10, 10, 'in_stock'),
(2, 3, 20, 20, 'in_stock'),
(3, 4, 8, 8, 'in_stock');
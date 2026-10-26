import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.extensions import db
from app.models.user import User, Role
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.stock_transaction import StockTransaction, TransactionType
from app.models.audit_log import AuditLog


def create_initial_admin(username="admin", password="AdminPassword123!", full_name="System Administrator"):
    """Creates default administrator account if one does not exist."""
    admin = User.query.filter_by(username=username).first()
    if not admin:
        admin = User(
            username=username,
            full_name=full_name,
            role=Role.ADMIN,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Created initial administrator account: {username}")
    return admin


def seed_database(reset_first=False):
    """
    Populates deterministic demo data:
    - Admin and Staff accounts
    - 5 Categories
    - 4 Suppliers
    - 24 Diverse Products across In-Stock, Low-Stock, and Out-of-Stock states
    - ~60 Realistic historical stock transactions spread over the past 45 days
    """
    if reset_first:
        print("Resetting database schema...")
        db.drop_all()
        db.create_all()

    # 1. Users
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            full_name="Alex Rivera (Administrator)",
            role=Role.ADMIN,
            is_active=True
        )
        admin.set_password("Admin123!")
        db.session.add(admin)

    staff = User.query.filter_by(username="staff").first()
    if not staff:
        staff = User(
            username="staff",
            full_name="Jordan Lee (Warehouse Staff)",
            role=Role.STAFF,
            is_active=True
        )
        staff.set_password("Staff123!")
        db.session.add(staff)

    db.session.commit()

    # Check if already seeded products
    if Product.query.count() > 0:
        print("Database already contains product records. Skipping demo population.")
        return

    # 2. Categories
    category_data = [
        ("Electronics & Components", "Semiconductors, microcontrollers, passive elements, and sensors."),
        ("Office & Computer Supplies", "Peripherals, ergonomics, toner, networking, and paper stationery."),
        ("Industrial Tools & Hardware", "Fasteners, power tools, measuring instruments, and shop supplies."),
        ("Safety & PPE Equipment", "Helmets, high-vis vests, respirators, eye protection, and gloves."),
        ("Packaging & Materials", "Cartons, bubble wrap, stretch film, pallets, and shipping tags."),
    ]

    categories = {}
    for name, desc in category_data:
        cat = Category.query.filter_by(name=name).first()
        if not cat:
            cat = Category(name=name, description=desc)
            db.session.add(cat)
            db.session.flush()
        categories[name] = cat

    # 3. Suppliers
    supplier_data = [
        ("Apex Global Logistics", "Marcus Vance", "+1 (555) 234-8901", "marcus@apexlogistics.com", "450 Industrial Parkway, Chicago, IL"),
        ("TechCore Components", "Elena Rostova", "+1 (555) 789-1234", "sales@techcorecomp.com", "1280 Silicon Way, San Jose, CA"),
        ("Precision Hardware Co.", "David Chen", "+1 (555) 345-6789", "d.chen@precisiontools.com", "88 Forge Road, Cleveland, OH"),
        ("SafeShield Industrial", "Sarah Jenkins", "+1 (555) 901-2345", "contact@safeshieldgear.com", "2100 Safety Blvd, Houston, TX"),
    ]

    suppliers = {}
    for name, contact, phone, email, addr in supplier_data:
        sup = Supplier.query.filter_by(name=name).first()
        if not sup:
            sup = Supplier(name=name, contact_person=contact, phone=phone, email=email, address=addr)
            db.session.add(sup)
            db.session.flush()
        suppliers[name] = sup

    db.session.commit()

    # 4. Products (24 items: 16 Healthy, 5 Low Stock, 3 Out of Stock)
    # (SKU, Name, Cat, Sup, Cost, Price, InitialStock, ReorderLevel)
    products_seed = [
        # Electronics
        ("EL-ARD-001", "Arduino Uno R3 Development Board", "Electronics & Components", "TechCore Components", Decimal("12.50"), Decimal("24.99"), 45, 15),
        ("EL-ESP-002", "ESP32 Wi-Fi & Bluetooth MCU", "Electronics & Components", "TechCore Components", Decimal("4.20"), Decimal("9.50"), 8, 12),  # Low stock
        ("EL-RAS-003", "Raspberry Pi 4 Model B (4GB)", "Electronics & Components", "TechCore Components", Decimal("45.00"), Decimal("65.00"), 0, 10),  # Out of stock
        ("EL-SEN-004", "DHT22 Digital Temperature Sensor", "Electronics & Components", "TechCore Components", Decimal("3.10"), Decimal("6.80"), 60, 20),
        ("EL-SOL-005", "Lead-Free Solder Wire Spool 100g", "Electronics & Components", "Precision Hardware Co.", Decimal("8.50"), Decimal("14.99"), 25, 10),

        # Office Supplies
        ("OF-MOU-101", "Logitech Wireless Optical Mouse", "Office & Computer Supplies", "Apex Global Logistics", Decimal("14.00"), Decimal("26.50"), 35, 10),
        ("OF-KEY-102", "Mechanical Backlit USB Keyboard", "Office & Computer Supplies", "Apex Global Logistics", Decimal("32.00"), Decimal("59.99"), 18, 10),
        ("OF-MON-103", "Dell 24-inch IPS FHD Monitor", "Office & Computer Supplies", "Apex Global Logistics", Decimal("95.00"), Decimal("149.99"), 4, 8),  # Low stock
        ("OF-CAB-104", "Cat6 Gigabit Ethernet Cable (15m)", "Office & Computer Supplies", "Apex Global Logistics", Decimal("5.50"), Decimal("11.99"), 50, 15),
        ("OF-TON-105", "High-Yield Black Laser Toner Cartridge", "Office & Computer Supplies", "Apex Global Logistics", Decimal("28.00"), Decimal("49.99"), 0, 5),  # Out of stock

        # Industrial Tools
        ("TL-DRI-201", "DeWalt 20V Cordless Brushless Drill", "Industrial Tools & Hardware", "Precision Hardware Co.", Decimal("85.00"), Decimal("139.00"), 14, 6),
        ("TL-CAL-202", "Mitutoyo 6-inch Digital Caliper", "Industrial Tools & Hardware", "Precision Hardware Co.", Decimal("72.00"), Decimal("115.00"), 9, 5),
        ("TL-HEX-203", "Metric Hex Key Ball-End Set (9pc)", "Industrial Tools & Hardware", "Precision Hardware Co.", Decimal("11.00"), Decimal("22.50"), 30, 12),
        ("TL-SCR-204", "M4 Stainless Steel Machine Screws (100pk)", "Industrial Tools & Hardware", "Precision Hardware Co.", Decimal("4.50"), Decimal("9.99"), 6, 15),  # Low stock
        ("TL-TOR-205", "Adjustable Torque Wrench 1/2-inch Drive", "Industrial Tools & Hardware", "Precision Hardware Co.", Decimal("48.00"), Decimal("89.00"), 12, 5),

        # Safety & PPE
        ("SF-HEL-301", "Vented Hard Hat with Ratchet Suspension", "Safety & PPE Equipment", "SafeShield Industrial", Decimal("16.00"), Decimal("29.99"), 40, 15),
        ("SF-GLO-302", "Nitrile Coated Work Gloves (Pack of 12)", "Safety & PPE Equipment", "SafeShield Industrial", Decimal("14.50"), Decimal("27.00"), 5, 15),  # Low stock
        ("SF-EYE-303", "Anti-Fog UV Safety Goggles", "Safety & PPE Equipment", "SafeShield Industrial", Decimal("5.00"), Decimal("11.50"), 55, 20),
        ("SF-RES-304", "N95 Particulate Respirator Box (20pk)", "Safety & PPE Equipment", "SafeShield Industrial", Decimal("18.00"), Decimal("32.50"), 0, 10),  # Out of stock
        ("SF-VST-305", "High-Visibility Reflective Safety Vest (L)", "Safety & PPE Equipment", "SafeShield Industrial", Decimal("7.50"), Decimal("14.99"), 38, 12),

        # Packaging
        ("PK-BOX-401", "Heavy-Duty Corrugated Shipping Box (12x12x8)", "Packaging & Materials", "Apex Global Logistics", Decimal("1.20"), Decimal("2.80"), 120, 40),
        ("PK-BUB-402", "Bubble Cushioning Wrap Roll (300ft)", "Packaging & Materials", "Apex Global Logistics", Decimal("19.00"), Decimal("34.99"), 22, 10),
        ("PK-TAP-403", "Industrial Packing Tape Roll (6pk)", "Packaging & Materials", "Apex Global Logistics", Decimal("9.50"), Decimal("18.00"), 4, 15),  # Low stock
        ("PK-STP-404", "Pallet Stretch Wrap Film (18-inch roll)", "Packaging & Materials", "Apex Global Logistics", Decimal("15.00"), Decimal("28.50"), 19, 8),
    ]

    created_products = []
    for sku, name, cat_name, sup_name, cost, price, stock, reorder in products_seed:
        prod = Product(
            sku=sku,
            name=name,
            description=f"Standard commercial grade {name}. Fully traceable inventory item.",
            category_id=categories[cat_name].id,
            supplier_id=suppliers[sup_name].id,
            unit_cost=cost,
            selling_price=price,
            quantity=stock,
            reorder_level=reorder,
            is_active=True
        )
        db.session.add(prod)
        created_products.append(prod)

    db.session.commit()

    # 5. Generate realistic historical stock transactions
    # We will simulate ~50 transactions over the past 40 days
    now = datetime.now(timezone.utc)
    rng = random.Random(42)  # Deterministic seed for reproducible testing

    print(f"Creating historical transactions across {len(created_products)} products...")

    for prod in created_products:
        # Initial stock receiving ~40 days ago
        base_days_ago = rng.randint(35, 45)
        initial_time = now - timedelta(days=base_days_ago, hours=rng.randint(1, 10))
        initial_qty = prod.quantity + rng.randint(20, 60)

        tx_init = StockTransaction(
            product_id=prod.id,
            user_id=admin.id,
            transaction_type=TransactionType.STOCK_IN,
            quantity=initial_qty,
            previous_quantity=0,
            resulting_quantity=initial_qty,
            unit_cost=prod.unit_cost,
            reference=f"PO-INIT-{prod.id:03d}",
            notes="Initial bulk warehouse consignment receipt.",
            created_at=initial_time
        )
        db.session.add(tx_init)

        # Intermittent stock issues (sales/deployments)
        running_balance = initial_qty
        num_sales = rng.randint(2, 5)
        for i in range(num_sales):
            issue_days_ago = rng.randint(2, base_days_ago - 2)
            issue_time = now - timedelta(days=issue_days_ago, hours=rng.randint(1, 18))
            
            # Sale size
            issue_qty = rng.randint(3, max(4, running_balance // 3))
            if issue_qty >= running_balance:
                issue_qty = max(1, running_balance - 1)
            
            if issue_qty > 0 and running_balance > 0:
                prev = running_balance
                running_balance -= issue_qty

                tx_out = StockTransaction(
                    product_id=prod.id,
                    user_id=staff.id,
                    transaction_type=TransactionType.STOCK_OUT,
                    quantity=issue_qty,
                    previous_quantity=prev,
                    resulting_quantity=running_balance,
                    unit_cost=prod.unit_cost,
                    reference=f"SO-2026-{rng.randint(1000, 9999)}",
                    notes="Client fulfillment dispatch.",
                    created_at=issue_time
                )
                db.session.add(tx_out)

    # Add audit log entry
    audit = AuditLog(
        user_id=admin.id,
        action="SEED_DATABASE",
        entity_type="System",
        entity_id="ALL",
        details="Populated deterministic demo dataset with 24 products and historical transactions."
    )
    db.session.add(audit)

    db.session.commit()
    print("Database seeding completed successfully.")

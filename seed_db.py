"""
Database Seeding Script for StockPulse Inventory & Stock Analysis System.
Populates deterministic demo dataset (Categories, Suppliers, Products, Stock Movements).
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app
from app.seed import seed_database, create_initial_admin

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    app = create_app()
    with app.app_context():
        print(f"Seeding database (reset={reset})...")
        seed_database(reset_first=reset)
        create_initial_admin("admin", "Admin123!", "Alex Rivera (Administrator)")
        print("\nDemo Accounts Created:")
        print("  Administrator: Username: admin  | Password: Admin123!")
        print("  Warehouse Staff: Username: staff | Password: Staff123!")
        print("\nDatabase is ready for evaluation.")

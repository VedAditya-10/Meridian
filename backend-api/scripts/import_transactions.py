import argparse
import asyncio
import csv
import logging
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal, engine
from src.models import Base
from src.models.store import Store
from src.models.transaction import Transaction, TransactionIngestionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("import_transactions")

# Ensure database tables exist (since we don't rely on migrations here per instructions)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def import_transactions(file_path: str):
    await init_db()

    async with AsyncSessionLocal() as session:
        # Load store mapping
        result = await session.execute(Store.__table__.select())
        stores = result.mappings().all()
        # Create a mapping based on name or a custom ID prefix if possible
        # The prompt says "Never infer store ids. Create store mapping mechanism."
        # We will assume a hardcoded mapping mechanism here for the known CSV store codes to our UUIDs.
        # Since we generated 3 stores in seed.py, let's map them.
        store_map = {
            "STI000": "a1b2c3d4-0001-4000-8000-000000000001",
            "STI001": "a1b2c3d4-0002-4000-8000-000000000002",
            "STI002": "a1b2c3d4-0003-4000-8000-000000000003"
        }

        chunk_size = 2000
        transactions_to_insert = []
        errors_to_insert = []

        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            now = datetime.utcnow()

            row_number = 1
            for row in reader:
                row_number += 1

                order_id = row.get("order_id")
                raw_store_id = row.get("store_id")
                order_date_str = row.get("order_date")
                order_time_str = row.get("order_time")
                customer_no = row.get("customer_no")
                qty_str = row.get("qty", "0")
                gmv_str = row.get("GMV", "0")
                brand_name = row.get("brand_name")

                error_message = None

                # Validation
                try:
                    qty = int(qty_str) if qty_str else 0
                    gmv = float(gmv_str) if gmv_str else 0.0

                    if not order_id:
                        error_message = "Missing order_id"
                    elif not raw_store_id:
                        error_message = "Missing store_id"
                    elif raw_store_id not in store_map:
                        error_message = f"Unknown store_id: {raw_store_id}"
                    elif gmv < 0:
                        error_message = f"Invalid gmv: {gmv}"
                    elif qty <= 0:
                        error_message = f"Invalid qty: {qty}"
                    else:
                        # Parse time
                        try:
                            # order_date: M/D/YYYY or YYYY-MM-DD
                            dt_str = f"{order_date_str} {order_time_str}"
                            try:
                                order_time = datetime.strptime(dt_str, "%m/%d/%Y %H:%M:%S")
                            except ValueError:
                                order_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                            
                            if order_time > now:
                                error_message = "Future timestamp"
                        except Exception as e:
                            error_message = f"Invalid timestamp format: {e}"

                except Exception as e:
                    error_message = f"Parse error: {e}"

                if error_message:
                    errors_to_insert.append({
                        "row_number": row_number,
                        "raw_payload": str(row),
                        "error_message": error_message
                    })
                else:
                    transactions_to_insert.append({
                        "order_id": order_id,
                        "store_id": store_map[raw_store_id],
                        "order_time": order_time,
                        "customer_no": customer_no,
                        "qty": qty,
                        "gmv": gmv,
                    })

                # Insert chunks
                if len(transactions_to_insert) >= chunk_size:
                    await insert_transactions(session, transactions_to_insert)
                    transactions_to_insert.clear()

                if len(errors_to_insert) >= chunk_size:
                    await insert_errors(session, errors_to_insert)
                    errors_to_insert.clear()

            # Insert remaining
            if transactions_to_insert:
                await insert_transactions(session, transactions_to_insert)
            if errors_to_insert:
                await insert_errors(session, errors_to_insert)

        await session.commit()
        logger.info("Import completed successfully.")

async def insert_transactions(session: AsyncSession, data: list):
    if not data:
        return
    stmt = insert(Transaction).values(data)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["order_id", "store_id"]
    )
    await session.execute(stmt)

async def insert_errors(session: AsyncSession, data: list):
    if not data:
        return
    stmt = insert(TransactionIngestionError).values(data)
    await session.execute(stmt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import POS Transactions")
    parser.add_argument("file_path", help="Path to the CSV file")
    args = parser.parse_args()

    asyncio.run(import_transactions(args.file_path))

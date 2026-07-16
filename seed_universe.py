# one command to pour seed_data into every store; idempotent, safe to re-run
import seed_data
from app import billing, crm, orders, store


def main() -> None:
    crm.init_crm()
    crm.seed_crm(seed_data.CUSTOMERS)
    orders.init_orders()
    orders.seed_orders(seed_data.CUSTOMERS)
    billing.init_billing()
    billing.seed_billing(seed_data.CUSTOMERS)
    store.init_db()
    store.seed_history(seed_data.CUSTOMERS)
    print(f"seeded universe: {len(seed_data.CUSTOMERS)} customers")


if __name__ == "__main__":
    main()

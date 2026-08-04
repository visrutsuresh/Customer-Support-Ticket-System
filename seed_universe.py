# one command to pour seed_data into every store; idempotent, safe to re-run
import seed_data
from app import customer_data, store


def main() -> None:
    customer_data.init_crm()
    customer_data.seed_crm(seed_data.CUSTOMERS)
    customer_data.init_orders()
    customer_data.seed_orders(seed_data.CUSTOMERS)
    customer_data.init_billing()
    customer_data.seed_billing(seed_data.CUSTOMERS)
    store.init_db()
    store.seed_history(seed_data.CUSTOMERS)
    print(f"seeded universe: {len(seed_data.CUSTOMERS)} customers")


if __name__ == "__main__":
    main()

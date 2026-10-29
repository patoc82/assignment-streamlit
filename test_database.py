
from database import (
    get_supabase_client,
    get_customers,
    get_products,
)

try:
    client = get_supabase_client()
    print("Supabase client created.")

    for table_name, fetch_function in [
        ("customers", get_customers),
        ("products", get_products),
    ]:
        try:
            records = fetch_function(client)
            print(f"\nTable: {table_name}")
            print(f"Records returned: {len(records)}")

            if records:
                print("First record:", records[0])
            else:
                print("The API returned an empty list.")

        except Exception as error:
            print(f"\nTable: {table_name}")
            print("Query failed.")
            print("Error type:", type(error).__name__)
            print("Error details:", str(error))

except Exception as error:
    print("Client initialization failed.")
    print("Error type:", type(error).__name__)
    print("Error details:", str(error))
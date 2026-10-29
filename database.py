import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


load_dotenv()


def get_setting(name):
    """Read a setting from Streamlit secrets or local environment."""
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        # Streamlit secrets may not be configured locally.
        pass

    return os.getenv(name)


def get_supabase_client():
    """Create a Supabase client using configured credentials."""
    url = get_setting("SUPABASE_URL")
    key = get_setting("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are missing. "
            "Configure SUPABASE_URL and SUPABASE_KEY."
        )

    return create_client(url, key)


def get_customers(client):
    response = (
        client.table("customers")
        .select("customer_id, name, email, city")
        .order("customer_id")
        .execute()
    )
    return response.data or []


def get_products(client):
    response = (
        client.table("products")
        .select("product_id, product_name, category, price")
        .order("product_id")
        .execute()
    )
    return response.data or []


def get_orders(client):
    response = (
        client.table("orders")
        .select(
            "order_id, customer_id, product_id, "
            "quantity, order_date, unit_price"
        )
        .order("order_id", desc=True)
        .execute()
    )
    return response.data or []


def get_current_product(client, product_id):
    """Read the current price directly from Supabase."""
    response = (
        client.table("products")
        .select("product_id, product_name, category, price")
        .eq("product_id", product_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise ValueError(
            "The selected product no longer exists. Refresh the data."
        )

    return response.data[0]


def insert_order(client, customer_id, product_id, quantity, unit_price):
    """Insert one order and return its generated ID."""
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise ValueError("Quantity must be a whole number.")

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    payload = {
        "customer_id": customer_id,
        "product_id": product_id,
        "quantity": quantity,
        "order_date": date.today().isoformat(),
        "unit_price": str(unit_price),
    }

    response = (
        client.table("orders")
        .insert(payload)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the inserted order."
        )

    order = response.data[0]

    if order.get("order_id") is None:
        raise RuntimeError(
            "The order was inserted, but no generated order ID was returned. "
            "Do not submit it again. Check the database."
        )

    return order["order_id"]


def verify_order(client, order_id):
    """Verify a saved order with a new database query."""
    response = (
        client.table("orders")
        .select(
            "order_id, customer_id, product_id, "
            "quantity, order_date, unit_price"
        )
        .eq("order_id", order_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]
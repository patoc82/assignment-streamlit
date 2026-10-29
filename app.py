# Streamlit interface
## Each order should contain one product, with one or more units.

import streamlit as st
import pandas as pd
from decimal import Decimal, InvalidOperation

from database import (
    get_supabase_client,
    get_customers,
    get_products,
    get_orders,
    get_current_product,
    insert_order,
    verify_order,
)


# --------------------------------------------------
# Page setup
# --------------------------------------------------

st.set_page_config(
    page_title="Supabase Order Entry",
    page_icon="📦",
    layout="wide",
)

st.title("Customer Order Entry")
st.write(
    "Select a customer and product, review the order, "
    "and confirm the purchase. Orders are stored in Supabase."
)


# --------------------------------------------------
# Password gate: runs before any database access
# --------------------------------------------------

def get_app_password():
    try:
        password = st.secrets.get("APP_PASSWORD")
        if password:
            return password
    except Exception:
        pass

    import os
    from dotenv import load_dotenv

    load_dotenv()
    return os.getenv("APP_PASSWORD")


required_password = get_app_password()

if not required_password:
    st.error(
        "App access is not configured. "
        "The administrator must set APP_PASSWORD."
    )
    st.stop()

if not st.session_state.get("authorized", False):
    st.subheader("Classroom Access")

    with st.form("access_form"):
        entered_password = st.text_input(
            "Enter the classroom password",
            type="password",
        )
        login_clicked = st.form_submit_button("Access Application")

    if login_clicked:
        if entered_password == required_password:
            st.session_state["authorized"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


# --------------------------------------------------
# Session state
# --------------------------------------------------

if "reviewed_order" not in st.session_state:
    st.session_state["reviewed_order"] = None

if "review_version" not in st.session_state:
    st.session_state["review_version"] = 0

if "last_saved_order_id" not in st.session_state:
    st.session_state["last_saved_order_id"] = None

if "verification_result" not in st.session_state:
    st.session_state["verification_result"] = None

if "verification_status" not in st.session_state:
    st.session_state["verification_status"] = None

if "refresh_requested" not in st.session_state:
    st.session_state["refresh_requested"] = False


# --------------------------------------------------
# Database connection and data retrieval
# --------------------------------------------------

@st.cache_resource
def create_database_client():
    return get_supabase_client()


def money(value):
    return f"${Decimal(str(value)):,.2f}"


def decimal_value(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("Invalid numeric value.")
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("A valid numeric price was not returned.")


def load_data():
    client = create_database_client()
    customers = get_customers(client)
    products = get_products(client)
    orders = get_orders(client)
    return client, customers, products, orders


try:
    client, customers, products, orders = load_data()
except Exception as e:
    st.error("Unable to retrieve data from Supabase.")
    st.write("Error type:", type(e).__name__)
    st.code(str(e))
    st.stop()



# --------------------------------------------------
# Refresh button
# --------------------------------------------------

if st.button("Refresh Data", key="refresh_data"):
    st.session_state["refresh_requested"] = True
    st.session_state["reviewed_order"] = None
    st.session_state["review_version"] += 1
    st.rerun()

if st.session_state["refresh_requested"]:
    st.success("Data refreshed from Supabase.")
    st.session_state["refresh_requested"] = False


# --------------------------------------------------
# Customer and product tables
# --------------------------------------------------

st.header("Customers")

customer_table = pd.DataFrame(
    [
        {
            "Customer ID": c["customer_id"],
            "Name": c["name"],
        }
        for c in customers
    ],
    columns=["Customer ID", "Name"],
)

st.dataframe(customer_table, hide_index=True, use_container_width=True)


st.header("Products")

product_table = pd.DataFrame(
    [
        {
            "Product ID": p["product_id"],
            "Product Name": p["product_name"],
            "Category": p["category"],
            "Price": money(p["price"]),
        }
        for p in products
    ],
    columns=["Product ID", "Product Name", "Category", "Price"],
)

st.dataframe(product_table, hide_index=True, use_container_width=True)


# --------------------------------------------------
# Order entry
# --------------------------------------------------

st.divider()
st.header("Create an Order")

if not customers:
    st.warning("No customers were returned by Supabase.")
    st.stop()

if not products:
    st.warning("No products were returned by Supabase.")
    st.stop()


customer_by_id = {
    c["customer_id"]: c for c in customers
}

product_by_id = {
    p["product_id"]: p for p in products
}


with st.form("order_selection_form"):
    selected_customer_id = st.selectbox(
        "Select Customer",
        options=list(customer_by_id.keys()),
        format_func=lambda cid: (
            f'{customer_by_id[cid]["name"]} '
            f'(ID: {cid})'
        ),
    )

    selected_product_id = st.selectbox(
        "Select Product",
        options=list(product_by_id.keys()),
        format_func=lambda pid: (
            f'{product_by_id[pid]["product_name"]} '
            f'(ID: {pid})'
        ),
    )

    quantity = st.number_input(
        "Quantity",
        min_value=1,
        value=1,
        step=1,
    )

    review_clicked = st.form_submit_button("Review Order")


if review_clicked:
    try:
        current_product = get_current_product(
            client, selected_product_id
        )

        st.session_state["reviewed_order"] = {
            "customer_id": selected_customer_id,
            "product_id": selected_product_id,
            "quantity": int(quantity),
            "product_name": current_product["product_name"],
            "unit_price": str(
                decimal_value(current_product["price"])
            ),
        }

        st.session_state["review_version"] += 1

    except Exception:
        st.error(
            "Unable to retrieve the current product price. "
            "Refresh the data and try again."
        )


# --------------------------------------------------
# Review and confirmation
# --------------------------------------------------

review = st.session_state["reviewed_order"]

if review is not None:
    customer = customer_by_id.get(review["customer_id"])

    if customer is None or review["product_id"] not in product_by_id:
        st.warning(
            "The selected customer or product is no longer "
            "available. Refresh the data and review again."
        )
        st.session_state["reviewed_order"] = None
        st.stop()

    unit_price = decimal_value(review["unit_price"])
    total_price = unit_price * review["quantity"]

    st.subheader("Review Your Order")

    review_table = pd.DataFrame(
        [
            {
                "Customer": customer["name"],
                "Product": review["product_name"],
                "Quantity": review["quantity"],
                "Unit Price": money(unit_price),
                "Total Price": money(total_price),
            }
        ]
    )

    st.dataframe(
        review_table,
        hide_index=True,
        use_container_width=True,
    )

    st.warning(
        "Confirm the details below. The price will be checked "
        "again before the order is saved."
    )

    confirmation_key = (
        f'confirm_order_{st.session_state["review_version"]}'
    )

    with st.form(
        f'confirmation_form_{st.session_state["review_version"]}'
    ):
        confirmed = st.checkbox(
            "I confirm that these order details are correct.",
            key=confirmation_key,
        )

        submit_clicked = st.form_submit_button("Confirm and Submit Order")

    if submit_clicked:
        if not confirmed:
            st.error("Check the confirmation box before submitting.")
        else:
            try:
                # Recheck the product price immediately before insertion.
                latest_product = get_current_product(
                    client, review["product_id"]
                )

                latest_price = decimal_value(latest_product["price"])
                reviewed_price = decimal_value(review["unit_price"])

                if latest_price != reviewed_price:
                    review["unit_price"] = str(latest_price)
                    review["product_name"] = latest_product["product_name"]

                    st.session_state["reviewed_order"] = review
                    st.session_state["review_version"] += 1

                    st.warning(
                        "The product price changed. "
                        f"The updated unit price is {money(latest_price)} "
                        f"and the new total is "
                        f"{money(latest_price * review['quantity'])}. "
                        "Review the updated price and confirm again."
                    )

                else:
                    order_id = insert_order(
                        client=client,
                        customer_id=review["customer_id"],
                        product_id=review["product_id"],
                        quantity=review["quantity"],
                        unit_price=latest_price,
                    )

                    # Record the ID immediately so a verification
                    # failure never triggers an automatic resubmission.
                    st.session_state["last_saved_order_id"] = order_id
                    st.session_state["verification_result"] = None
                    st.session_state["verification_status"] = "pending"
                    st.session_state["reviewed_order"] = None
                    st.session_state["review_version"] += 1

                    try:
                        saved_order = verify_order(client, order_id)

                        if saved_order is None:
                            st.session_state["verification_status"] = "failed"
                            st.error(
                                f"Order {order_id} was saved, but the "
                                "database query did not retrieve it "
                                "for verification. Do not submit it again."
                            )
                        else:
                            st.session_state["verification_result"] = (
                                saved_order
                            )
                            st.session_state["verification_status"] = "verified"
                            st.success(
                                f"Order {order_id} saved and verified "
                                "successfully."
                            )

                    except Exception:
                        st.session_state["verification_status"] = "failed"
                        st.error(
                            f"Order {order_id} was saved, but verification "
                            "failed. Do not submit it again. Check the "
                            "database before taking further action."
                        )

                    # Refresh the data after a successful insertion.
                    try:
                        client, customers, products, orders = load_data()
                        customer_by_id = {
                            c["customer_id"]: c for c in customers
                        }
                        product_by_id = {
                            p["product_id"]: p for p in products
                        }
                    except Exception:
                        st.warning(
                            "The order was submitted, but the latest "
                            "tables could not be refreshed."
                        )
                        st.exception(refresh_error)

            except ValueError as error:
                st.error(str(error))
            except Exception as error:
                st.error(
                    "The order could not be confirmed as saved. "
                    "Check Supabase before trying again to avoid "
                    "creating a duplicate order."
                )
                st.write("Error type:", type(error).__name__)
                st.code(str(error))


# --------------------------------------------------
# Verification table: data from the separate API query
# --------------------------------------------------

st.divider()
st.header("Saved Order Verification")

saved_order = st.session_state["verification_result"]

if saved_order is not None:
    saved_customer = customer_by_id.get(saved_order["customer_id"])
    saved_product = product_by_id.get(saved_order["product_id"])

    stored_unit_price = decimal_value(saved_order["unit_price"])
    stored_quantity = int(saved_order["quantity"])

    verification_table = pd.DataFrame(
        [
            {
                "Order ID": saved_order["order_id"],
                "Customer": (
                    saved_customer["name"] if saved_customer else
                    str(saved_order["customer_id"])
                ),
                "Product": (
                    saved_product["product_name"] if saved_product else
                    str(saved_order["product_id"])
                ),
                "Quantity": stored_quantity,
                "Unit Price": money(stored_unit_price),
                "Total": money(stored_unit_price * stored_quantity),
                "Order Date": saved_order["order_date"],
            }
        ]
    )

    st.dataframe(
        verification_table,
        hide_index=True,
        use_container_width=True,
    )

elif st.session_state["verification_status"] == "failed":
    st.info(
        "The last order was saved, but its verification record "
        "could not be retrieved."
    )
else:
    st.caption(
        "After you submit an order, its independently retrieved "
        "database record will appear here."
    )


# --------------------------------------------------
# Order history and optional customer filter
# --------------------------------------------------

st.divider()
st.header("Order History")

if not orders:
    st.info("No orders have been returned by Supabase.")
else:
    customer_options = ["All Customers"] + list(customer_by_id.keys())

    selected_history_customer = st.selectbox(
        "Filter Order History by Customer",
        options=customer_options,
        format_func=lambda cid: (
            "All Customers"
            if cid == "All Customers"
            else (
                f'{customer_by_id[cid]["name"]} (ID: {cid})'
                if cid in customer_by_id
                else str(cid)
            )
        ),
        key="history_customer_filter",
    )

    history_rows = []

    for order in orders:
        cid = order["customer_id"]
        pid = order["product_id"]

        if (
            selected_history_customer != "All Customers"
            and cid != selected_history_customer
        ):
            continue

        stored_price = decimal_value(order["unit_price"])
        stored_quantity = int(order["quantity"])

        history_rows.append(
            {
                "Order ID": order["order_id"],
                "Customer": (
                    customer_by_id[cid]["name"]
                    if cid in customer_by_id else str(cid)
                ),
                "Product": (
                    product_by_id[pid]["product_name"]
                    if pid in product_by_id else str(pid)
                ),
                "Quantity": stored_quantity,
                "Unit Price": money(stored_price),
                "Total": money(stored_price * stored_quantity),
                "Order Date": order["order_date"],
            }
        )

    history_table = pd.DataFrame(
        history_rows,
        columns=[
            "Order ID",
            "Customer",
            "Product",
            "Quantity",
            "Unit Price",
            "Total",
            "Order Date",
        ],
    )

    st.dataframe(
        history_table,
        hide_index=True,
        use_container_width=True,
    )

    filtered_total = sum(
        (
            decimal_value(order["unit_price"]) * int(order["quantity"])
            for order in orders
            if (
              selected_history_customer == "All Customers"
             or order["customer_id"] == selected_history_customer
            )
        ),
        Decimal("0.00"),
)

    st.metric("Total Order Value", money(filtered_total))
import streamlit as st
import sqlite3
from pathlib import Path
from datetime import datetime, date
import html

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Double 2 Fast Food",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "restaurant.db"

RESTAURANT_NAME = "DOUBLE 2 FAST FOOD"
RESTAURANT_PHONE = "0300-1234567"
RESTAURANT_ADDRESS = "Main Road, Karachi"


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row is not None


def get_columns(conn, table_name):
    if not table_exists(conn, table_name):
        return []
    rows = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
    return [row["name"] for row in rows]


def find_table(conn, names):
    for name in names:
        if table_exists(conn, name):
            return name
    return None


# ============================================================
# CREATE ONLY MISSING SUPPORT TABLES
# Existing restaurant.db is NEVER replaced.
# ============================================================

def setup_database():
    conn = get_connection()

    # Existing product table is preferred.
    product_table = find_table(
        conn,
        ["products", "product", "food_items", "items"]
    )

    # If product table doesn't exist, create standard one.
    if not product_table:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            )
        """)

    # Sales support tables.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number INTEGER,
            sale_date TEXT NOT NULL,
            sale_time TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            cash_received REAL NOT NULL,
            change_amount REAL NOT NULL,
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            customer_address TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            customer_bill_printed INTEGER DEFAULT 0,
            kitchen_slip_printed INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            item_total REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Default settings.
    defaults = {
        "restaurant_name": RESTAURANT_NAME,
        "restaurant_phone": RESTAURANT_PHONE,
        "restaurant_address": RESTAURANT_ADDRESS,
    }

    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
            (key, value)
        )

    conn.commit()
    conn.close()


setup_database()


# ============================================================
# SETTINGS
# ============================================================

def get_setting(key, default=""):
    conn = get_connection()

    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

        if row:
            return row["value"]

        return default

    except Exception:
        return default

    finally:
        conn.close()


def save_setting(key, value):
    conn = get_connection()

    conn.execute("""
        INSERT INTO settings(key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value=excluded.value
    """, (key, str(value)))

    conn.commit()
    conn.close()


restaurant_name = get_setting(
    "restaurant_name",
    RESTAURANT_NAME
)

restaurant_phone = get_setting(
    "restaurant_phone",
    RESTAURANT_PHONE
)

restaurant_address = get_setting(
    "restaurant_address",
    RESTAURANT_ADDRESS
)


# ============================================================
# PRODUCT TABLE DETECTION
# ============================================================

def get_product_table_info():
    conn = get_connection()

    table = find_table(
        conn,
        ["products", "product", "food_items", "items"]
    )

    if not table:
        conn.close()
        return None, []

    columns = get_columns(conn, table)
    conn.close()

    return table, columns


def get_product_column(columns, possible):
    lower_map = {c.lower(): c for c in columns}

    for name in possible:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

    return None


# ============================================================
# PRODUCTS
# ============================================================

def get_products():
    conn = get_connection()

    try:
        table, columns = get_product_table_info()

        if not table:
            return []

        id_col = get_product_column(
            columns,
            ["id", "product_id"]
        )

        name_col = get_product_column(
            columns,
            ["name", "product_name", "item_name"]
        )

        price_col = get_product_column(
            columns,
            ["price", "product_price"]
        )

        category_col = get_product_column(
            columns,
            ["category", "product_category"]
        )

        available_col = get_product_column(
            columns,
            ["available", "is_available", "active", "status"]
        )

        if not name_col or not price_col:
            return []

        query = f"""
            SELECT
                {f'[{id_col}]' if id_col else 'rowid'} AS id,
                [{name_col}] AS name,
                [{price_col}] AS price,
                {f'[{category_col}]' if category_col else "''"} AS category,
                {f'[{available_col}]' if available_col else '1'} AS available
            FROM [{table}]
            ORDER BY id
        """

        rows = conn.execute(query).fetchall()

        products = []

        for row in rows:
            available = row["available"]

            if isinstance(available, str):
                available = (
                    available.lower()
                    not in ["0", "false", "no", "inactive"]
                )

            else:
                available = bool(available)

            products.append({
                "id": row["id"],
                "name": row["name"],
                "price": float(row["price"] or 0),
                "category": row["category"] or "Other",
                "available": available,
            })

        return products

    finally:
        conn.close()


def add_product(name, price, category):
    conn = get_connection()

    try:
        table, columns = get_product_table_info()

        if not table:
            return False, "Product table not found."

        name_col = get_product_column(
            columns,
            ["name", "product_name", "item_name"]
        )

        price_col = get_product_column(
            columns,
            ["price", "product_price"]
        )

        category_col = get_product_column(
            columns,
            ["category", "product_category"]
        )

        available_col = get_product_column(
            columns,
            ["available", "is_available", "active"]
        )

        if not name_col or not price_col:
            return False, "Required product columns not found."

        exists = conn.execute(
            f"SELECT 1 FROM [{table}] WHERE [{name_col}]=?",
            (name,)
        ).fetchone()

        if exists:
            return False, "Product already exists."

        cols = [name_col, price_col]
        values = [name, price]

        if category_col:
            cols.append(category_col)
            values.append(category)

        if available_col:
            cols.append(available_col)
            values.append(1)

        placeholders = ",".join(["?"] * len(values))

        conn.execute(
            f"""
            INSERT INTO [{table}]
            ({",".join(f"[{c}]" for c in cols)})
            VALUES ({placeholders})
            """,
            values
        )

        conn.commit()

        return True, "Product added."

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


def update_product(product_id, name, price, category, available=True):
    conn = get_connection()

    try:
        table, columns = get_product_table_info()

        id_col = get_product_column(
            columns,
            ["id", "product_id"]
        )

        name_col = get_product_column(
            columns,
            ["name", "product_name", "item_name"]
        )

        price_col = get_product_column(
            columns,
            ["price", "product_price"]
        )

        category_col = get_product_column(
            columns,
            ["category", "product_category"]
        )

        available_col = get_product_column(
            columns,
            ["available", "is_available", "active"]
        )

        if not id_col:
            return False, "ID column not found."

        updates = []
        values = []

        if name_col:
            updates.append(f"[{name_col}]=?")
            values.append(name)

        if price_col:
            updates.append(f"[{price_col}]=?")
            values.append(price)

        if category_col:
            updates.append(f"[{category_col}]=?")
            values.append(category)

        if available_col:
            updates.append(f"[{available_col}]=?")
            values.append(1 if available else 0)

        values.append(product_id)

        conn.execute(
            f"""
            UPDATE [{table}]
            SET {",".join(updates)}
            WHERE [{id_col}]=?
            """,
            values
        )

        conn.commit()

        return True, "Product updated."

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


def delete_product(product_id):
    conn = get_connection()

    try:
        table, columns = get_product_table_info()

        id_col = get_product_column(
            columns,
            ["id", "product_id"]
        )

        if not id_col:
            return False, "ID column not found."

        conn.execute(
            f"DELETE FROM [{table}] WHERE [{id_col}]=?",
            (product_id,)
        )

        conn.commit()

        return True, "Product deleted."

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


# ============================================================
# BILL NUMBER
# ============================================================

def get_next_bill_number():
    conn = get_connection()

    try:
        row = conn.execute(
            "SELECT MAX(bill_number) AS max_bill FROM sales"
        ).fetchone()

        return int(row["max_bill"] or 0) + 1

    finally:
        conn.close()


# ============================================================
# SALE
# ============================================================

def save_sale(
    bill_number,
    sale_date,
    sale_time,
    subtotal,
    discount,
    total,
    cash_received,
    change_amount,
    items,
    customer_name="",
    customer_phone="",
    customer_address="",
    notes="",
    customer_bill_printed=0,
    kitchen_slip_printed=0,
):
    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO sales (
                bill_number,
                sale_date,
                sale_time,
                subtotal,
                discount,
                total,
                cash_received,
                change_amount,
                customer_name,
                customer_phone,
                customer_address,
                notes,
                customer_bill_printed,
                kitchen_slip_printed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bill_number,
            sale_date,
            sale_time,
            subtotal,
            discount,
            total,
            cash_received,
            change_amount,
            customer_name,
            customer_phone,
            customer_address,
            notes,
            customer_bill_printed,
            kitchen_slip_printed,
        ))

        sale_id = cursor.lastrowid

        for item in items:
            quantity = int(item["quantity"])
            price = float(item["price"])
            item_total = quantity * price

            conn.execute("""
                INSERT INTO sale_items (
                    sale_id,
                    product_name,
                    quantity,
                    price,
                    item_total
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                sale_id,
                item["name"],
                quantity,
                price,
                item_total,
            ))

        conn.commit()

        return sale_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_sales_between(start_date, end_date):
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT *
            FROM sales
            WHERE sale_date BETWEEN ? AND ?
            ORDER BY id DESC
        """, (
            start_date,
            end_date
        )).fetchall()

    finally:
        conn.close()


def get_sale(sale_id):
    conn = get_connection()

    try:
        return conn.execute(
            "SELECT * FROM sales WHERE id=?",
            (sale_id,)
        ).fetchone()

    finally:
        conn.close()


def get_sale_items(sale_id):
    conn = get_connection()

    try:
        return conn.execute("""
            SELECT *
            FROM sale_items
            WHERE sale_id=?
            ORDER BY id
        """, (sale_id,)).fetchall()

    finally:
        conn.close()


# ============================================================
# SESSION STATE
# ============================================================

if "cart" not in st.session_state:
    st.session_state.cart = {}

if "page" not in st.session_state:
    st.session_state.page = "POS"

if "selected_category" not in st.session_state:
    st.session_state.selected_category = "All"

if "show_preview" not in st.session_state:
    st.session_state.show_preview = False

if "last_order" not in st.session_state:
    st.session_state.last_order = None


# ============================================================
# CART
# ============================================================

def add_to_cart(name, price):
    if name in st.session_state.cart:
        st.session_state.cart[name]["quantity"] += 1
    else:
        st.session_state.cart[name] = {
            "quantity": 1,
            "price": float(price)
        }


def increase_quantity(name):
    if name in st.session_state.cart:
        st.session_state.cart[name]["quantity"] += 1


def decrease_quantity(name):
    if name in st.session_state.cart:
        st.session_state.cart[name]["quantity"] -= 1

        if st.session_state.cart[name]["quantity"] <= 0:
            del st.session_state.cart[name]


def remove_from_cart(name):
    if name in st.session_state.cart:
        del st.session_state.cart[name]


def clear_cart():
    st.session_state.cart = {}


def get_subtotal():
    total = 0

    for data in st.session_state.cart.values():
        total += data["quantity"] * data["price"]

    return total


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    text-align: center;
    font-size: 36px;
    font-weight: 800;
    margin-bottom: 5px;
}

.section-title {
    font-size: 23px;
    font-weight: 700;
    margin-top: 10px;
}

.product-card button {
    min-height: 105px !important;
}

div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 12px;
}

.bill-box {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 15px;
    background: white;
}

.receipt {
    background: white;
    color: black;
    width: 80mm;
    padding: 10px;
    font-family: "Courier New", monospace;
    font-size: 13px;
    margin: auto;
}

.receipt h2,
.receipt h3 {
    text-align: center;
    margin: 3px;
}

.receipt-line {
    border-top: 1px dashed black;
    margin: 7px 0;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

with st.sidebar:

    st.markdown(
        f"## 🍔 {restaurant_name}"
    )

    st.divider()

    page = st.radio(
        "MENU",
        [
            "POS / New Bill",
            "Product Management",
            "Sales Report",
            "Bill History",
            "Settings",
        ],
        index=[
            "POS / New Bill",
            "Product Management",
            "Sales Report",
            "Bill History",
            "Settings",
        ].index(
            {
                "POS": "POS / New Bill",
                "Products": "Product Management",
                "Sales": "Sales Report",
                "History": "Bill History",
                "Settings": "Settings",
            }.get(
                st.session_state.page,
                "POS / New Bill"
            )
        )
    )

    if page == "POS / New Bill":
        st.session_state.page = "POS"
    elif page == "Product Management":
        st.session_state.page = "Products"
    elif page == "Sales Report":
        st.session_state.page = "Sales"
    elif page == "Bill History":
        st.session_state.page = "History"
    else:
        st.session_state.page = "Settings"

    st.divider()

    st.caption("Double 2 Fast Food POS")
    st.caption("SQLite Database • Offline")


# ============================================================
# POS
# ============================================================

if st.session_state.page == "POS":

    st.markdown(
        f'<div class="main-title">🍔 {restaurant_name}</div>',
        unsafe_allow_html=True
    )

    st.caption(
        f"{restaurant_phone}  •  {restaurant_address}"
    )

    st.divider()

    products = get_products()

    left, right = st.columns([1.65, 1], gap="large")

    # --------------------------------------------------------
    # LEFT PRODUCTS
    # --------------------------------------------------------

    with left:

        st.markdown(
            '<div class="section-title">🍔 FOOD ITEMS</div>',
            unsafe_allow_html=True
        )

        available_products = [
            p for p in products
            if p["available"]
        ]

        categories = sorted(
            set(
                p["category"]
                for p in available_products
            )
        )

        category_options = ["All"] + categories

        selected_category = st.selectbox(
            "Category",
            category_options,
            key="category_select"
        )

        if selected_category == "All":
            filtered_products = available_products
        else:
            filtered_products = [
                p for p in available_products
                if p["category"] == selected_category
            ]

        search = st.text_input(
            "🔎 Search Food Item",
            placeholder="Search product..."
        )

        if search:
            filtered_products = [
                p for p in filtered_products
                if search.lower() in p["name"].lower()
            ]

        if not filtered_products:
            st.info("No products available.")
        else:

            # 3-column product buttons, same basic layout as old POS.
            for i in range(0, len(filtered_products), 3):

                cols = st.columns(3)

                for j, col in enumerate(cols):

                    index = i + j

                    if index >= len(filtered_products):
                        break

                    product = filtered_products[index]

                    with col:

                        if st.button(
                            f"🍔 {product['name']}\n\nRs. {product['price']:.0f}",
                            key=f"product_{product['id']}",
                            use_container_width=True,
                        ):
                            add_to_cart(
                                product["name"],
                                product["price"]
                            )
                            st.rerun()

    # --------------------------------------------------------
    # RIGHT CURRENT ORDER
    # --------------------------------------------------------

    with right:

        st.markdown(
            '<div class="section-title">🧾 CURRENT ORDER</div>',
            unsafe_allow_html=True
        )

        if not st.session_state.cart:

            st.info(
                "No items in current order.\n\n"
                "Click food items to add them."
            )

        else:

            for name, data in list(
                st.session_state.cart.items()
            ):

                quantity = data["quantity"]
                price = data["price"]
                item_total = quantity * price

                c1, c2, c3, c4, c5 = st.columns(
                    [2.7, 0.7, 0.7, 1.1, 1.2]
                )

                with c1:
                    st.write(
                        f"**{name}**"
                    )

                with c2:
                    if st.button(
                        "-",
                        key=f"minus_{name}"
                    ):
                        decrease_quantity(name)
                        st.rerun()

                with c3:
                    st.markdown(
                        f"**{quantity}**"
                    )

                with c4:
                    if st.button(
                        "+",
                        key=f"plus_{name}"
                    ):
                        increase_quantity(name)
                        st.rerun()

                with c5:
                    st.write(
                        f"Rs. {item_total:.0f}"
                    )

            st.divider()

            subtotal = get_subtotal()

            discount = st.number_input(
                "Discount (Rs.)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="discount"
            )

            if discount > subtotal:
                discount = subtotal

            total = max(
                0,
                subtotal - discount
            )

            st.metric(
                "Subtotal",
                f"Rs. {subtotal:.0f}"
            )

            st.metric(
                "TOTAL",
                f"Rs. {total:.0f}"
            )

            cash = st.number_input(
                "Cash Received (Rs.)",
                min_value=0.0,
                value=0.0,
                step=50.0,
                key="cash"
            )

            if cash >= total:
                change = cash - total

                st.success(
                    f"Change: Rs. {change:.0f}"
                )

            else:
                change = 0

                if cash > 0:
                    st.error(
                        f"Insufficient Cash: "
                        f"Rs. {total - cash:.0f} more required"
                    )

            st.divider()

            customer_name = st.text_input(
                "Customer Name",
                key="customer_name"
            )

            customer_phone = st.text_input(
                "Contact Number",
                key="customer_phone"
            )

            customer_address = st.text_input(
                "Address",
                key="customer_address"
            )

            notes = st.text_area(
                "Notes",
                key="order_notes",
                height=70
            )

            b1, b2 = st.columns(2)

            with b1:

                if st.button(
                    "🗑️ CLEAR BILL",
                    use_container_width=True
                ):
                    clear_cart()

                    for key in [
                        "discount",
                        "cash",
                        "customer_name",
                        "customer_phone",
                        "customer_address",
                        "order_notes",
                    ]:
                        if key in st.session_state:
                            del st.session_state[key]

                    st.rerun()

            with b2:

                if st.button(
                    "✅ DONE ORDER",
                    type="primary",
                    use_container_width=True
                ):

                    if cash < total:

                        st.error(
                            "Cash received is less than total."
                        )

                    else:

                        now = datetime.now()

                        bill_number = get_next_bill_number()

                        sale_date = now.strftime(
                            "%Y-%m-%d"
                        )

                        sale_time = now.strftime(
                            "%H:%M:%S"
                        )

                        items = []

                        for name, data in (
                            st.session_state.cart.items()
                        ):

                            items.append({
                                "name": name,
                                "quantity": data["quantity"],
                                "price": data["price"],
                            })

                        st.session_state.last_order = {
                            "bill_number": bill_number,
                            "sale_date": sale_date,
                            "sale_time": sale_time,
                            "subtotal": subtotal,
                            "discount": discount,
                            "total": total,
                            "cash": cash,
                            "change": change,
                            "items": items,
                            "customer_name": customer_name,
                            "customer_phone": customer_phone,
                            "customer_address": customer_address,
                            "notes": notes,
                        }

                        st.session_state.show_preview = True

                        st.rerun()


# ============================================================
# ORDER PREVIEW
# ============================================================

if (
    st.session_state.page == "POS"
    and st.session_state.show_preview
    and st.session_state.last_order
):

    order = st.session_state.last_order

    st.divider()

    st.markdown(
        f"## 🧾 Order Preview — Bill #{order['bill_number']}"
    )

    customer_col, kitchen_col = st.columns(2)

    # --------------------------------------------------------
    # CUSTOMER BILL
    # --------------------------------------------------------

    with customer_col:

        st.subheader("CUSTOMER BILL")

        receipt_lines = []

        receipt_lines.append(
            "=" * 38
        )

        receipt_lines.append(
            restaurant_name.center(38)
        )

        receipt_lines.append(
            "=" * 38
        )

        receipt_lines.append(
            f"Contact: {restaurant_phone}"
        )

        receipt_lines.append(
            f"Address: {restaurant_address}"
        )

        if order["customer_name"]:
            receipt_lines.append(
                f"Customer: {order['customer_name']}"
            )

        if order["customer_phone"]:
            receipt_lines.append(
                f"Phone: {order['customer_phone']}"
            )

        if order["customer_address"]:
            receipt_lines.append(
                f"Delivery: {order['customer_address']}"
            )

        receipt_lines.append("")

        receipt_lines.append(
            f"Bill No: {order['bill_number']}"
        )

        receipt_lines.append(
            f"Date: {order['sale_date']}"
        )

        receipt_lines.append(
            f"Time: {order['sale_time']}"
        )

        receipt_lines.append(
            "-" * 38
        )

        for item in order["items"]:

            name = item["name"][:18]
            qty = item["quantity"]
            price = item["price"]
            total_item = qty * price

            receipt_lines.append(
                f"{name:<18} "
                f"{qty:>3} "
                f"{price:>6.0f} "
                f"{total_item:>7.0f}"
            )

        receipt_lines.append(
            "-" * 38
        )

        receipt_lines.append(
            f"{'Subtotal:':<27}"
            f"Rs. {order['subtotal']:.0f}"
        )

        receipt_lines.append(
            f"{'Discount:':<27}"
            f"Rs. {order['discount']:.0f}"
        )

        receipt_lines.append(
            f"{'TOTAL:':<27}"
            f"Rs. {order['total']:.0f}"
        )

        receipt_lines.append("")

        receipt_lines.append(
            f"{'Cash:':<27}"
            f"Rs. {order['cash']:.0f}"
        )

        receipt_lines.append(
            f"{'Change:':<27}"
            f"Rs. {order['change']:.0f}"
        )

        if order["notes"]:
            receipt_lines.append("")
            receipt_lines.append(
                f"Notes: {order['notes']}"
            )

        receipt_lines.append("")
        receipt_lines.append(
            "THANK YOU!".center(38)
        )

        receipt_lines.append(
            "VISIT AGAIN".center(38)
        )

        receipt_lines.append(
            "=" * 38
        )

        customer_bill_text = "\n".join(
            receipt_lines
        )

        st.code(
            customer_bill_text,
            language=None
        )

    # --------------------------------------------------------
    # KITCHEN SLIP
    # --------------------------------------------------------

    with kitchen_col:

        st.subheader("KITCHEN SLIP")

        kitchen_lines = []

        kitchen_lines.append(
            "=" * 38
        )

        kitchen_lines.append(
            restaurant_name.center(38)
        )

        kitchen_lines.append(
            "KITCHEN ORDER".center(38)
        )

        kitchen_lines.append(
            "=" * 38
        )

        kitchen_lines.append(
            f"Order #: {order['bill_number']}"
        )

        kitchen_lines.append(
            f"Date: {order['sale_date']}"
        )

        kitchen_lines.append(
            f"Time: {order['sale_time']}"
        )

        kitchen_lines.append(
            "-" * 38
        )

        for item in order["items"]:

            name = item["name"][:28]

            kitchen_lines.append(
                f"{name:<28} x {item['quantity']}"
            )

        kitchen_lines.append(
            "-" * 38
        )

        kitchen_lines.append(
            "PREPARE ORDER".center(38)
        )

        kitchen_lines.append(
            "=" * 38
        )

        kitchen_slip_text = "\n".join(
            kitchen_lines
        )

        st.code(
            kitchen_slip_text,
            language=None
        )

    st.divider()

    st.subheader("PRINT OPTIONS")

    print_kitchen = st.checkbox(
        "🖨️ Print Kitchen Slip",
        value=True
    )

    print_customer = st.checkbox(
        "🖨️ Print Customer Bill",
        value=False
    )

    # --------------------------------------------------------
    # PRINTABLE HTML
    # --------------------------------------------------------

    def make_print_html(title, text):
        safe = html.escape(text)

        return f"""
        <html>
        <head>
        <title>{html.escape(title)}</title>

        <style>
        body {{
            margin: 0;
            padding: 0;
            background: white;
        }}

        .receipt {{
            width: 80mm;
            margin: auto;
            padding: 5mm;
            box-sizing: border-box;
            font-family: "Courier New", monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }}

        @media print {{
            @page {{
                size: 80mm auto;
                margin: 0;
            }}

            body {{
                width: 80mm;
            }}

            .receipt {{
                width: 80mm;
            }}
        }}
        </style>
        </head>

        <body>
        <div class="receipt">{safe}</div>

        <script>
        window.onload = function() {{
            window.print();
        }};
        </script>

        </body>
        </html>
        """

    print_col1, print_col2 = st.columns(2)

    with print_col1:

        if print_kitchen:

            st.download_button(
                "📄 Kitchen Slip",
                kitchen_slip_text,
                file_name=f"kitchen_{order['bill_number']}.txt",
                mime="text/plain",
                use_container_width=True
            )

    with print_col2:

        if print_customer:

            st.download_button(
                "📄 Customer Bill",
                customer_bill_text,
                file_name=f"bill_{order['bill_number']}.txt",
                mime="text/plain",
                use_container_width=True
            )

    # Browser print buttons.
    st.markdown("### 🖨️ Browser Print")

    import streamlit.components.v1 as components

    if print_kitchen:

        components.html(
            make_print_html(
                "Kitchen Slip",
                kitchen_slip_text
            ),
            height=1,
        )

    if print_customer:

        components.html(
            make_print_html(
                "Customer Bill",
                customer_bill_text
            ),
            height=1,
        )

    st.divider()

    save_col, cancel_col = st.columns(2)

    with save_col:

        if st.button(
            "💾 SAVE ORDER",
            type="primary",
            use_container_width=True
        ):

            try:

                save_sale(
                    bill_number=order["bill_number"],
                    sale_date=order["sale_date"],
                    sale_time=order["sale_time"],
                    subtotal=order["subtotal"],
                    discount=order["discount"],
                    total=order["total"],
                    cash_received=order["cash"],
                    change_amount=order["change"],
                    items=order["items"],
                    customer_name=order["customer_name"],
                    customer_phone=order["customer_phone"],
                    customer_address=order["customer_address"],
                    notes=order["notes"],
                    customer_bill_printed=1 if print_customer else 0,
                    kitchen_slip_printed=1 if print_kitchen else 0,
                )

                st.success(
                    f"Bill #{order['bill_number']} saved successfully!"
                )

                clear_cart()

                st.session_state.show_preview = False
                st.session_state.last_order = None

                for key in [
                    "discount",
                    "cash",
                    "customer_name",
                    "customer_phone",
                    "customer_address",
                    "order_notes",
                ]:
                    if key in st.session_state:
                        del st.session_state[key]

                st.rerun()

            except Exception as e:

                st.error(
                    f"Database Error: {e}"
                )

    with cancel_col:

        if st.button(
            "❌ CANCEL",
            use_container_width=True
        ):

            st.session_state.show_preview = False
            st.session_state.last_order = None

            st.rerun()


# ============================================================
# PRODUCT MANAGEMENT
# ============================================================

elif st.session_state.page == "Products":

    st.title("📦 PRODUCT MANAGEMENT")

    st.caption(
        "Add, update, delete and manage food items."
    )

    products = get_products()

    with st.form("add_product_form"):

        st.subheader("ADD PRODUCT")

        c1, c2, c3 = st.columns(3)

        with c1:
            new_name = st.text_input(
                "Name"
            )

        with c2:
            new_price = st.number_input(
                "Price",
                min_value=0.0,
                step=10.0
            )

        with c3:
            new_category = st.text_input(
                "Category"
            )

        add_button = st.form_submit_button(
            "➕ ADD PRODUCT",
            type="primary"
        )

        if add_button:

            if (
                not new_name.strip()
                or not new_category.strip()
                or new_price <= 0
            ):

                st.error(
                    "Fill Name, Price and Category correctly."
                )

            else:

                success, message = add_product(
                    new_name.strip(),
                    new_price,
                    new_category.strip()
                )

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    st.divider()

    st.subheader(
        f"ALL PRODUCTS ({len(products)})"
    )

    if not products:

        st.info(
            "No products found in restaurant.db."
        )

    else:

        for product in products:

            c1, c2, c3, c4, c5, c6 = st.columns(
                [2.5, 1, 1.5, 1, 1, 1]
            )

            with c1:
                st.write(
                    f"**{product['name']}**"
                )

            with c2:
                st.write(
                    f"Rs. {product['price']:.0f}"
                )

            with c3:
                st.write(
                    product["category"]
                )

            with c4:

                status = (
                    "🟢 Available"
                    if product["available"]
                    else "🔴 Off"
                )

                st.write(status)

            with c5:

                if st.button(
                    "✏️ Edit",
                    key=f"edit_{product['id']}"
                ):
                    st.session_state[
                        f"editing_{product['id']}"
                    ] = True
                    st.rerun()

            with c6:

                if st.button(
                    "🗑️ Delete",
                    key=f"delete_{product['id']}"
                ):

                    success, message = delete_product(
                        product["id"]
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

            if st.session_state.get(
                f"editing_{product['id']}",
                False
            ):

                with st.form(
                    f"edit_form_{product['id']}"
                ):

                    ec1, ec2, ec3, ec4 = st.columns(4)

                    with ec1:
                        edit_name = st.text_input(
                            "Name",
                            value=product["name"],
                            key=f"ename_{product['id']}"
                        )

                    with ec2:
                        edit_price = st.number_input(
                            "Price",
                            min_value=0.0,
                            value=float(product["price"]),
                            key=f"eprice_{product['id']}"
                        )

                    with ec3:
                        edit_category = st.text_input(
                            "Category",
                            value=product["category"],
                            key=f"ecat_{product['id']}"
                        )

                    with ec4:
                        edit_available = st.checkbox(
                            "Available",
                            value=product["available"],
                            key=f"eavail_{product['id']}"
                        )

                    ec5, ec6 = st.columns(2)

                    with ec5:

                        update_button = st.form_submit_button(
                            "💾 UPDATE",
                            type="primary"
                        )

                    with ec6:

                        cancel_button = st.form_submit_button(
                            "CANCEL"
                        )

                    if update_button:

                        success, message = update_product(
                            product["id"],
                            edit_name.strip(),
                            edit_price,
                            edit_category.strip(),
                            edit_available
                        )

                        if success:
                            st.success(message)
                            st.session_state[
                                f"editing_{product['id']}"
                            ] = False
                            st.rerun()
                        else:
                            st.error(message)

                    if cancel_button:

                        st.session_state[
                            f"editing_{product['id']}"
                        ] = False

                        st.rerun()

            st.divider()


# ============================================================
# SALES REPORT
# ============================================================

elif st.session_state.page == "Sales":

    st.title("📊 SALES REPORT")

    today = date.today()

    mode = st.radio(
        "Report",
        [
            "Today",
            "This Month",
            "Custom"
        ],
        horizontal=True
    )

    if mode == "Today":

        start_date = today
        end_date = today

    elif mode == "This Month":

        start_date = today.replace(day=1)
        end_date = today

    else:

        c1, c2 = st.columns(2)

        with c1:
            start_date = st.date_input(
                "From",
                value=today
            )

        with c2:
            end_date = st.date_input(
                "To",
                value=today
            )

    if start_date > end_date:

        st.error(
            "From date cannot be after To date."
        )

    else:

        rows = get_sales_between(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

        orders = len(rows)

        sales = sum(
            float(row["total"])
            for row in rows
        )

        cash_total = sum(
            float(row["cash_received"])
            for row in rows
        )

        discount_total = sum(
            float(row["discount"])
            for row in rows
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Orders",
                orders
            )

        with c2:
            st.metric(
                "Sales",
                f"Rs. {sales:.0f}"
            )

        with c3:
            st.metric(
                "Discount",
                f"Rs. {discount_total:.0f}"
            )

        with c4:
            st.metric(
                "Cash",
                f"Rs. {cash_total:.0f}"
            )

        st.divider()

        if rows:

            display_rows = []

            for row in rows:

                display_rows.append({
                    "Bill": row["bill_number"],
                    "Date": row["sale_date"],
                    "Time": row["sale_time"],
                    "Total": f"Rs. {row['total']:.0f}",
                    "Cash": f"Rs. {row['cash_received']:.0f}",
                    "Change": f"Rs. {row['change_amount']:.0f}",
                    "Customer": row["customer_name"] or "",
                })

            st.dataframe(
                display_rows,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "No sales found for selected dates."
            )


# ============================================================
# BILL HISTORY
# ============================================================

elif st.session_state.page == "History":

    st.title("🧾 BILL HISTORY")

    search_bill = st.text_input(
        "Search Bill Number",
        placeholder="Enter bill number..."
    )

    conn = get_connection()

    try:

        if search_bill.strip():

            try:
                bill_no = int(search_bill)

                rows = conn.execute("""
                    SELECT *
                    FROM sales
                    WHERE bill_number=?
                    ORDER BY id DESC
                """, (bill_no,)).fetchall()

            except ValueError:

                rows = []

        else:

            rows = conn.execute("""
                SELECT *
                FROM sales
                ORDER BY id DESC
                LIMIT 500
            """).fetchall()

    finally:
        conn.close()

    if not rows:

        st.info(
            "No bills found."
        )

    else:

        for sale in rows:

            title = (
                f"Bill #{sale['bill_number']} "
                f"• {sale['sale_date']} "
                f"{sale['sale_time']} "
                f"• Rs. {sale['total']:.0f}"
            )

            with st.expander(title):

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    st.write(
                        f"**Bill:** #{sale['bill_number']}"
                    )

                with c2:
                    st.write(
                        f"**Total:** Rs. {sale['total']:.0f}"
                    )

                with c3:
                    st.write(
                        f"**Cash:** Rs. {sale['cash_received']:.0f}"
                    )

                with c4:
                    st.write(
                        f"**Change:** Rs. {sale['change_amount']:.0f}"
                    )

                if sale["customer_name"]:
                    st.write(
                        f"Customer: {sale['customer_name']}"
                    )

                if sale["customer_phone"]:
                    st.write(
                        f"Phone: {sale['customer_phone']}"
                    )

                items = get_sale_items(
                    sale["id"]
                )

                st.markdown("### Items")

                item_display = []

                for item in items:

                    item_display.append({
                        "Item": item["product_name"],
                        "Qty": item["quantity"],
                        "Price": f"Rs. {item['price']:.0f}",
                        "Total": f"Rs. {item['item_total']:.0f}",
                    })

                st.dataframe(
                    item_display,
                    use_container_width=True,
                    hide_index=True
                )

                st.write(
                    f"Subtotal: **Rs. {sale['subtotal']:.0f}**"
                )

                st.write(
                    f"Discount: **Rs. {sale['discount']:.0f}**"
                )

                st.write(
                    f"Total: **Rs. {sale['total']:.0f}**"
                )


# ============================================================
# SETTINGS
# ============================================================

elif st.session_state.page == "Settings":

    st.title("⚙️ SETTINGS")

    st.subheader(
        "Restaurant Information"
    )

    with st.form("settings_form"):

        name = st.text_input(
            "Restaurant Name",
            value=restaurant_name
        )

        phone = st.text_input(
            "Restaurant Phone",
            value=restaurant_phone
        )

        address = st.text_input(
            "Restaurant Address",
            value=restaurant_address
        )

        save_button = st.form_submit_button(
            "💾 SAVE SETTINGS",
            type="primary"
        )

        if save_button:

            save_setting(
                "restaurant_name",
                name
            )

            save_setting(
                "restaurant_phone",
                phone
            )

            save_setting(
                "restaurant_address",
                address
            )

            st.success(
                "Settings saved successfully."
            )

            st.rerun()

    st.divider()

    st.subheader("Database")

    st.write(
        f"Database: `{DB_PATH.name}`"
    )

    if DB_PATH.exists():

        size = DB_PATH.stat().st_size

        st.success(
            f"restaurant.db connected • "
            f"{size:,} bytes"
        )

    else:

        st.error(
            "restaurant.db not found."
        )

    st.info(
        "Your existing restaurant.db is used by this application. "
        "It is not deleted or replaced."
    )

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"

load_dotenv(PROJECT_ROOT / ".env")


@st.cache_resource
def get_engine():
    db_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "periodwise_db")
    )

    return create_engine(db_url, pool_pre_ping=True)


@st.cache_data(ttl=300)
def load_data():

    # On Streamlit Community Cloud, use cleaned CSV files.
    if not os.getenv("DB_PASSWORD"):

        sales = pd.read_csv(
            DATA_DIR / "sales_data_cleaned.csv"
        )

        products = pd.read_csv(
            DATA_DIR / "product_data_cleaned.csv"
        )

        prices = pd.read_csv(
            DATA_DIR / "price_observations_cleaned.csv"
        )
        survey = pd.read_csv(
            DATA_DIR / "survey_public_summary.csv"
        )
        return sales, products, prices, survey

    # On your laptop, continue using PostgreSQL.
    engine = get_engine()

    with engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar()

    print(f"Dashboard connected to PostgreSQL: {database_name}")

    tables = {
        "sales": "sales_data",
        "products": "products",
        "prices": "price_observations",
        "survey": "survey_preferences"
    }

    data = {}

    for name, table in tables.items():
        query = text(f'SELECT * FROM "{table}"')

        with engine.connect() as connection:
            data[name] = pd.read_sql(query, connection)

    return (
        data["sales"],
        data["products"],
        data["prices"],
        data["survey"]
    )

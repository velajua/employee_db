from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.url import URL
import os

database_url = URL.create(
    "mysql+mysqlconnector",
    username=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST"),
    database="pruebaglobant"
)

engine = create_engine(database_url)

metadata = MetaData(bind=engine)
metadata.reflect()

for table_name in metadata.tables:
    print(f"Schema for table: {table_name}")
    table = metadata.tables[table_name]
    for column in table.columns:
        print(f"Column: {column.name}, Type: {column.type}")
    print("\n\n")

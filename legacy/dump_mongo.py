import json
import os
from pymongo import MongoClient

CONNECTION_STRING = "mongodb+srv://sei:1ZNx0lp9mztM78CQ@seiunotrade.obksnk6.mongodb.net/?retryWrites=true&w=majority&appName=SEIUNOTRADE"

def export_collection_to_json(collection, output_dir):
    data = list(collection.find())
    for doc in data:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
    collection_name = collection.name
    output_path = os.path.join(output_dir, f"{collection_name}.json")
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    print(f"Exported {collection_name} to {output_path}")

def export_database_to_json(uri, db_name, output_dir="mongo_dumps"):
    try:
        client = MongoClient(uri)
        db = client[db_name]

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        collections = db.list_collection_names()
        for collection_name in collections:
            collection = db[collection_name]
            export_collection_to_json(collection, output_dir)

        print(f"Exported database {db_name} to {output_dir} directory.")
    except Exception as e:
        print(f"Error exporting database: {str(e)}")
        raise

DB_NAME = "sei_database"
export_database_to_json(CONNECTION_STRING, DB_NAME)

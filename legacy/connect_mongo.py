from pymongo import MongoClient

CONNECTION_STRING = "mongodb+srv://sei:1ZNx0lp9mztM78CQ@seiunotrade.obksnk6.mongodb.net/?retryWrites=true&w=majority&appName=SEIUNOTRADE"


def get_database(db_name="sei_database"):
    try:
        client = MongoClient(CONNECTION_STRING)
        db = client[db_name]
        return db
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        raise

#! /usr/bin/env python3

import sys
import argparse
from pymongo import MongoClient

def backup_database(src_uri: str, dest_uri: str, source_db_name: str, target_db_name: str, force: bool = False, batch_size: int = 1000) -> None:
    """
    Backup MongoDB database to another database.

    Args:
        src_uri: Source MongoDB connection URI
        dest_uri: Destination MongoDB connection URI
        source_db_name: Name of the source database
        target_db_name: Name of the target database to create
        force: If True, drop the target database before backup
    """
    src_client = None
    dest_client = None

    try:
        # Connect to MongoDB servers
        src_client = MongoClient(src_uri)
        dest_client = MongoClient(dest_uri)

        # Get source and target database references
        source_db = src_client[source_db_name]
        target_db = dest_client[target_db_name]

        # Drop target database if force is enabled
        if force:
            print(f"Force option enabled. Dropping target database '{target_db_name}'")
            dest_client.drop_database(target_db_name)
            # Get a fresh reference after dropping
            target_db = dest_client[target_db_name]

        print(f"List of collections in source database: '{source_db_name}'")

        # Get list of all collections in source database
        collections = source_db.list_collection_names()

        print(f"Starting backup from '{source_db_name}' to '{target_db_name}'")
        print(f"Source URI: {src_uri}")
        print(f"Destination URI: {dest_uri}")
        print(f"Found {len(collections)} collections to backup")

        # Copy each collection in batches
        for collection_name in collections:
            print(f"Backing up collection: {collection_name}")

            total = source_db[collection_name].count_documents({})
            if total == 0:
                print("✓ Collection is empty")
                continue

            copied = 0
            batch = []
            for doc in source_db[collection_name].find():
                batch.append(doc)
                if len(batch) >= batch_size:
                    target_db[collection_name].insert_many(batch)
                    copied += len(batch)
                    print(f"  {copied}/{total} documents copied...")
                    batch = []

            if batch:
                target_db[collection_name].insert_many(batch)
                copied += len(batch)
            print(f"✓ Copied {copied} documents")

        print("\nBackup completed successfully!")

    except Exception as e:
        print(f"Error during backup: {str(e)}")
        sys.exit(1)
    finally:
        if src_client:
            src_client.close()
        if dest_client:
            dest_client.close()

def main():
    parser = argparse.ArgumentParser(description='Backup MongoDB database to another database.')
    parser.add_argument('--src-uri', required=True, help='Source MongoDB connection URI')
    parser.add_argument('--dest-uri', help='Destination MongoDB connection URI (defaults to source URI if not specified)')
    parser.add_argument('--src', required=True, help='Source database name')
    parser.add_argument('--dest', required=True, help='Destination database name')
    parser.add_argument('-f', '--force', action='store_true', help='Force drop the target database before backup')
    parser.add_argument('--batch-size', type=int, default=1000, help='Number of documents per insert batch (default: 1000)')

    args = parser.parse_args()

    if args.src == args.dest and args.src_uri == (args.dest_uri or args.src_uri):
        print("Error: Source and destination databases must be different when using the same MongoDB instance")
        sys.exit(1)

    # Use source URI as destination URI if not specified
    dest_uri = args.dest_uri or args.src_uri

    backup_database(args.src_uri, dest_uri, args.src, args.dest, args.force, args.batch_size)

if __name__ == "__main__":
    main()
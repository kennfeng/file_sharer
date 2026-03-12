import os
import time
import requests
import argparse
from dotenv import load_dotenv

load_dotenv()

RENDER_API_URL = "https://api.render.com/v1"

def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def get_owner_id(api_key):
    """Fetches the first available owner ID from Render."""
    response = requests.get(f"{RENDER_API_URL}/owners", headers=get_headers(api_key))
    response.raise_for_status()
    owners = response.json()
    if not owners:
        raise Exception("No owners found for this API key.")
    return owners[0]['owner']['id']

def create_postgres(api_key, name, database_name=None, plan="free"):
    """Creates a new Postgres instance."""
    owner_id = get_owner_id(api_key)
    payload = {
        "databaseName": database_name or name.replace("-", "_"),
        "databaseUser": "db_user",
        "ownerId": owner_id,
        "name": name,
        "plan": plan,
        "region": "oregon", 
        "version": "16"
    }
    print(f"Creating Postgres instance '{name}'...")
    response = requests.post(f"{RENDER_API_URL}/postgres", json=payload, headers=get_headers(api_key))
    response.raise_for_status()
    return response.json()['id']

def wait_for_ready(api_key, db_id):
    """Polls until database is available."""
    print("Waiting for database to become available...")
    while True:
        response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
        status = response.json().get('status')
        if status == 'available':
            print("Database ready")
            break
        time.sleep(15)

def get_connection_urls(api_key, db_id):
    """Fetches connection strings."""
    response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}/connection-info", headers=get_headers(api_key))
    return response.json()

def list_postgres(api_key):
    """Lists all Postgres instances."""
    response = requests.get(f"{RENDER_API_URL}/postgres", headers=get_headers(api_key))
    return response.json()

def delete_postgres(api_key, db_id):
    """Deletes a Postgres instance."""
    print(f"Deleting old database (ID: {db_id})...")
    requests.delete(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))

def list_services(api_key):
    """Lists all services."""
    response = requests.get(f"{RENDER_API_URL}/services", headers=get_headers(api_key))
    return response.json()

def update_render_env_var(api_key, service_id, key, value):
    """Updates an env var for a Render service."""
    print(f"Updating Service ({service_id}) environment variable '{key}'...")
    payload = {"value": value}
    response = requests.put(f"{RENDER_API_URL}/services/{service_id}/env-vars/{key}", json=payload, headers=get_headers(api_key))
    response.raise_for_status()

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    remake_parser = subparsers.add_parser("remake")
    remake_parser.add_argument("--name", required=True)
    remake_parser.add_argument("--service-name", required=True)
    remake_parser.add_argument("--plan", default="free")

    args = parser.parse_args()
    api_key = os.getenv("RENDER_API_KEY")

    if args.command == "remake":
        services = list_services(api_key)
        match = next((s for s in services if s['service']['name'] == args.service_name), None)
        if not match: raise Exception(f"Service {args.service_name} not found")
        service_id = match['service']['id']

        databases = list_postgres(api_key)
        old_db = next((d for d in databases if d['database']['name'] == args.name), None)
        if old_db: delete_postgres(api_key, old_db['database']['id'])

        db_id = create_postgres(api_key, args.name, plan=args.plan)
        wait_for_ready(api_key, db_id)
        
        urls = get_connection_urls(api_key, db_id)
        update_render_env_var(api_key, service_id, "DATABASE_URL", urls.get('externalConnectionURL'))

if __name__ == "__main__":
    main()

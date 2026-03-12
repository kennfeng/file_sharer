import os
import time
import requests
import argparse

RENDER_API_URL = "https://api.render.com/v1"

def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def get_owner_id(api_key):
    response = requests.get(f"{RENDER_API_URL}/owners", headers=get_headers(api_key))
    response.raise_for_status()
    owners = response.json()
    return owners[0]['owner']['id']

def create_postgres(api_key, name, plan="free"):
    owner_id = get_owner_id(api_key)
    payload = {
        "databaseName": name.replace("-", "_"),
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
    return response.json().get('id') or response.json().get('database', {}).get('id')

def wait_for_ready(api_key, db_id):
    print("Waiting for database to become available...")
    while True:
        response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
        data = response.json()
        # Handle both nested and flat responses
        status = data.get('status') or data.get('database', {}).get('status')
        if status == 'available':
            print("Database ready")
            break
        time.sleep(15)

def get_connection_urls(api_key, db_id):
    response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}/connection-info", headers=get_headers(api_key))
    return response.json()

def list_postgres(api_key):
    response = requests.get(f"{RENDER_API_URL}/postgres", headers=get_headers(api_key))
    return response.json()

def delete_postgres(api_key, db_id):
    print(f"Deleting old database (ID: {db_id})...")
    requests.delete(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))

def list_services(api_key):
    response = requests.get(f"{RENDER_API_URL}/services", headers=get_headers(api_key))
    return response.json()

def update_render_env_var(api_key, service_id, key, value):
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
        services_resp = list_services(api_key)
        service_match = None
        for s in services_resp:
            item = s.get('service') or s
            if item.get('name') == args.service_name:
                service_match = item
                break
        
        if not service_match: raise Exception(f"Service {args.service_name} not found")
        service_id = service_match['id']

        databases_resp = list_postgres(api_key)
        old_db_id = None
        for d in databases_resp:
            item = d.get('database') or d
            if item.get('name') == args.name:
                old_db_id = item['id']
                break
        
        if old_db_id: delete_postgres(api_key, old_db_id)

        db_id = create_postgres(api_key, args.name, plan=args.plan)
        wait_for_ready(api_key, db_id)
        
        urls = get_connection_urls(api_key, db_id)
        update_render_env_var(api_key, service_id, "DATABASE_URL", urls.get('externalConnectionURL'))
        print("Done")

if __name__ == "__main__":
    main()

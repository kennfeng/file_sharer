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
    return response.json()[0]['owner']['id']

def list_postgres(api_key):
    response = requests.get(f"{RENDER_API_URL}/postgres", headers=get_headers(api_key))
    response.raise_for_status()
    return response.json()

def delete_all_postgres(api_key):
    """Deletes ALL postgres databases (required for free tier's 1 DB limit)."""
    databases = list_postgres(api_key)
    if not databases:
        print("No existing databases found.")
        return
    for d in databases:
        item = d.get('database') or d
        db_id = item.get('id')
        db_name = item.get('name')
        print(f"Deleting database '{db_name}' (ID: {db_id})...")
        resp = requests.delete(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
        print(f"   Delete status: {resp.status_code}")
    print("Waiting 15 seconds for Render to process deletions...")
    time.sleep(15)

def create_postgres(api_key, name, plan="free"):
    owner_id = get_owner_id(api_key)
    payload = {
        "databaseName": "db_" + str(int(time.time()))[-6:],  # Always unique internal name
        "databaseUser": "db_user",
        "ownerId": owner_id,
        "name": name,
        "plan": plan,
        "region": "oregon",
        "version": "16"
    }
    print(f"Creating Postgres instance '{name}'...")
    response = requests.post(f"{RENDER_API_URL}/postgres", json=payload, headers=get_headers(api_key))
    
    if response.status_code == 409:
        print(f"Still got 409. Response: {response.text}")
        raise Exception("409 Conflict: A database still exists on the free tier. Check your Render dashboard manually.")
    
    response.raise_for_status()
    data = response.json()
    return data.get('id') or data.get('database', {}).get('id')

def wait_for_ready(api_key, db_id):
    print("Waiting for database to become available...")
    for _ in range(30):
        try:
            response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
            data = response.json()
            status = data.get('status') or data.get('database', {}).get('status')
            print(f"   Status: {status}")
            if status == 'available':
                print("Database is ready!")
                return
        except Exception as e:
            print(f"   Poll error: {e}")
        time.sleep(20)
    raise Exception("Timed out waiting for database.")

def list_services(api_key):
    response = requests.get(f"{RENDER_API_URL}/services", headers=get_headers(api_key))
    response.raise_for_status()
    return response.json()

def update_render_env_var(api_key, service_id, key, value):
    print(f"Updating env var '{key}'...")
    payload = {"value": value}
    response = requests.put(
        f"{RENDER_API_URL}/services/{service_id}/env-vars/{key}",
        json=payload,
        headers=get_headers(api_key)
    )
    response.raise_for_status()
    print("Env var updated")

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    remake_parser = subparsers.add_parser("remake")
    remake_parser.add_argument("--name", required=True)
    remake_parser.add_argument("--service-name", required=True)
    remake_parser.add_argument("--plan", default="free")

    args = parser.parse_args()
    api_key = os.getenv("RENDER_API_KEY")
    if not api_key:
        raise Exception("RENDER_API_KEY not set!")

    if args.command == "remake":
        print(f"Looking for service '{args.service_name}'...")
        services = list_services(api_key)
        service_match = None
        for s in services:
            item = s.get('service') or s
            print(f"   Found service: {item.get('name')}")
            if item.get('name') == args.service_name:
                service_match = item
                break
        if not service_match:
            raise Exception(f"Service '{args.service_name}' not found!")

        delete_all_postgres(api_key)

        db_id = create_postgres(api_key, args.name, plan=args.plan)
        wait_for_ready(api_key, db_id)

        conn_resp = requests.get(f"{RENDER_API_URL}/postgres/{db_id}/connection-info", headers=get_headers(api_key))
        conn_resp.raise_for_status()
        external_url = conn_resp.json().get('externalConnectionURL')
        print(f"External URL: {external_url}")
        
        update_render_env_var(api_key, service_match['id'], "DATABASE_URL", external_url)
        print("All done")

if __name__ == "__main__":
    main()

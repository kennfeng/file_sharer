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
    raw = response.json()
    print(f"📦 Raw postgres list response: {raw}")  # DEBUG: show exact format
    return raw

def delete_all_postgres(api_key):
    databases = list_postgres(api_key)
    if not databases:
        print("No existing databases found.")
        return

    for item in databases:
        # Try every possible key structure Render might return
        db_id   = item.get('id') or item.get('postgres', {}).get('id') or item.get('database', {}).get('id')
        db_name = item.get('name') or item.get('postgres', {}).get('name') or item.get('database', {}).get('name')
        
        if not db_id:
            print(f"⚠️ Could not extract ID from item: {item}")
            continue
        
        print(f"🗑️ Deleting '{db_name}' (ID: {db_id})...")
        resp = requests.delete(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
        print(f"   Delete status: {resp.status_code}")

    print("⏸️ Waiting 90 seconds for Render to fully process deletions...")
    time.sleep(90)

def create_postgres(api_key, base_name, plan="free"):
    owner_id = get_owner_id(api_key)
    # Use a timestamp suffix so the service name is ALWAYS unique
    unique_name = f"{base_name}-{int(time.time())}"
    payload = {
        "databaseName": "db_" + str(int(time.time()))[-6:],
        "databaseUser": "db_user",
        "ownerId": owner_id,
        "name": unique_name,
        "plan": plan,
        "region": "oregon",
        "version": "16"
    }
    print(f"🚀 Creating Postgres instance '{unique_name}'...")
    response = requests.post(f"{RENDER_API_URL}/postgres", json=payload, headers=get_headers(api_key))
    
    if not response.ok:
        print(f"❌ Create failed: {response.status_code} - {response.text}")
        response.raise_for_status()

    data = response.json()
    print(f"📦 Raw create response: {data}")  # DEBUG
    db_id = data.get('id') or data.get('postgres', {}).get('id') or data.get('database', {}).get('id')
    return db_id, unique_name

def wait_for_ready(api_key, db_id):
    print("⏳ Waiting for database to become available...")
    for _ in range(30):
        try:
            response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
            data = response.json()
            status = data.get('status') or data.get('postgres', {}).get('status') or data.get('database', {}).get('status')
            print(f"   Status: {status}")
            if status == 'available':
                print("✅ Database is ready!")
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
    print(f"🌐 Updating env var '{key}'...")
    payload = {"value": value}
    response = requests.put(
        f"{RENDER_API_URL}/services/{service_id}/env-vars/{key}",
        json=payload,
        headers=get_headers(api_key)
    )
    response.raise_for_status()
    print("✅ Env var updated!")

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
        # 1. Find the web service
        print(f"🔍 Looking for service '{args.service_name}'...")
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

        # 2. Delete ALL databases
        delete_all_postgres(api_key)

        # 3. Create fresh DB with unique name
        db_id, db_name = create_postgres(api_key, args.name, plan=args.plan)
        wait_for_ready(api_key, db_id)

        # 4. Update env var
        conn_resp = requests.get(f"{RENDER_API_URL}/postgres/{db_id}/connection-info", headers=get_headers(api_key))
        conn_resp.raise_for_status()
        external_url = conn_resp.json().get('externalConnectionURL')
        print(f"🔗 External URL: {external_url}")

        update_render_env_var(api_key, service_match['id'], "DATABASE_URL", external_url)
        print(f"✨ Done! New database '{db_name}' is live.")

if __name__ == "__main__":
    main()

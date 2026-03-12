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
    databases = list_postgres(api_key)
    if not databases:
        print("No existing databases found.")
        return
    for item in databases:
        # From debug: data is nested under 'postgres' key
        db = item.get('postgres') or item
        db_id   = db.get('id')
        db_name = db.get('name')
        if not db_id:
            print(f"⚠️ Could not extract ID from: {item}")
            continue
        print(f"🗑️ Deleting '{db_name}' (ID: {db_id})...")
        resp = requests.delete(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
        print(f"   Delete status: {resp.status_code}")
    print("⏸️ Waiting 90 seconds for Render to fully process deletions...")
    time.sleep(90)

def create_postgres(api_key, base_name, plan="free"):
    owner_id = get_owner_id(api_key)
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
    # From debug: create response is FLAT (no nesting)
    data = response.json()
    return data['id']

def wait_for_ready(api_key, db_id):
    print("⏳ Waiting for database to become available...")
    for _ in range(30):
        try:
            response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}", headers=get_headers(api_key))
            data = response.json()
            # From debug: status is flat on GET single DB too
            status = data.get('status') or data.get('postgres', {}).get('status')
            print(f"   Status: {status}")
            if status == 'available':
                print("✅ Database is ready!")
                return
        except Exception as e:
            print(f"   Poll error: {e}")
        time.sleep(20)
    raise Exception("Timed out waiting for database.")

def get_external_url(api_key, db_id):
    """Builds a full postgres:// URL from Render's connection-info."""
    response = requests.get(f"{RENDER_API_URL}/postgres/{db_id}/connection-info", headers=get_headers(api_key))
    response.raise_for_status()
    data = response.json()

    ext_string = data.get('externalConnectionString', '')
    password   = data.get('password', '')

    full_url = f"postgresql://db_user:{password}@{ext_string}"
    return full_url


def list_services(api_key):
    response = requests.get(f"{RENDER_API_URL}/services", headers=get_headers(api_key))
    response.raise_for_status()
    return response.json()

def update_render_env_var(api_key, service_id, key, value):
    """Uses the BULK env-var update endpoint which is more reliable."""
    print(f"🌐 Updating env var '{key}'...")
    # First get all existing env vars so we don't wipe them
    existing_resp = requests.get(
        f"{RENDER_API_URL}/services/{service_id}/env-vars",
        headers=get_headers(api_key)
    )
    existing = existing_resp.json() if existing_resp.ok else []
    print(f"   Existing env vars count: {len(existing)}")

    # Build the updated list
    env_vars = []
    found = False
    for e in existing:
        ev = e.get('envVar') or e
        if ev.get('key') == key:
            env_vars.append({"key": key, "value": value})
            found = True
        else:
            env_vars.append({"key": ev['key'], "value": ev.get('value', '')})
    if not found:
        env_vars.append({"key": key, "value": value})

    # PUT the full list back
    response = requests.put(
        f"{RENDER_API_URL}/services/{service_id}/env-vars",
        json=env_vars,
        headers=get_headers(api_key)
    )
    print(f"   Env var update status: {response.status_code} - {response.text[:200]}")
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
            if item.get('name') == args.service_name:
                service_match = item
                break
        if not service_match:
            raise Exception(f"Service '{args.service_name}' not found!")
        print(f"   ✅ Found service ID: {service_match['id']}")

        # 2. Delete ALL existing databases
        delete_all_postgres(api_key)

        # 3. Create fresh DB
        db_id = create_postgres(api_key, args.name, plan=args.plan)
        wait_for_ready(api_key, db_id)

        # 4. Get the external URL
        external_url = get_external_url(api_key, db_id)
        print(f"🔗 External URL: {external_url}")
        if not external_url:
            raise Exception("Could not find external URL in connection-info response!")

        # 5. Update the web service env var
        update_render_env_var(api_key, service_match['id'], "DATABASE_URL", external_url)
        print("✨ All done! Database refreshed and app updated.")

if __name__ == "__main__":
    main()

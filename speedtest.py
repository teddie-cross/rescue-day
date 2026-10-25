import time
import tomllib

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

t = time.time()
from supabase import create_client
print(f"Loading the library: {time.time() - t:.2f} s")

t = time.time()
client = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])
print(f"Connecting: {time.time() - t:.2f} s")

for i in range(3):
    t = time.time()
    client.table("site_data").select("content").eq("id", 1).execute()
    print(f"Database read {i + 1}: {time.time() - t:.2f} s")

    import socket
import time
import tomllib

from urllib.parse import urlparse

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

host = urlparse(secrets["SUPABASE_URL"]).hostname

t = time.time()
infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
print(f"Looking up the address: {time.time() - t:.2f} s ({len(infos)} results)")

for family, _, _, _, addr in infos:
    name = "IPv6" if family == socket.AF_INET6 else "IPv4"
    t = time.time()
    try:
        s = socket.create_connection(addr[:2], timeout=6)
        s.close()
        print(f"{name} connect: {time.time() - t:.2f} s")
    except Exception as e:
        print(f"{name} connect FAILED after {time.time() - t:.2f} s: {type(e).__name__}")

from supabase import create_client

client = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])
for wait in (0, 25, 25):
    if wait:
        print(f"Waiting {wait} s ...")
        time.sleep(wait)
    t = time.time()
    client.table("site_data").select("content").eq("id", 1).execute()
    print(f"Read after {wait} s idle: {time.time() - t:.2f} s")

t = time.time()
client2 = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])
client2.table("site_data").select("content").eq("id", 1).execute()
print(f"Brand new connection + read: {time.time() - t:.2f} s")

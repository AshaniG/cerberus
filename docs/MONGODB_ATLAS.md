# MongoDB Atlas setup (optional live mirror)

Cerberus keeps **SQLite** as the local source of truth (`data/cerberus.db`).
MongoDB Atlas is an **optional mirror** for cloud-style demos (Compass / supervisor
laptop). If Atlas is down or unset, the collector and dashboard still work.

## 1. Create a free cluster

1. Sign up at [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas).
2. Create a **M0 free** cluster (any cloud region close to you).
3. Create a database user (username + password). Save the password.
4. **Network Access** → add your Ubuntu machine’s public IP.  
   For a short home demo only, you may allow `0.0.0.0/0` — tighten it afterwards.

## 2. Connection string

In Atlas: **Connect** → **Drivers** → copy the URI, e.g.

```text
mongodb+srv://cerberus_user:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

Replace `<password>` with the real password (URL-encode special characters).

## 3. Configure Cerberus

```bash
cd /path/to/cerberus
cp .env.example .env
# edit .env:
#   MONGODB_URI=mongodb+srv://...
#   MONGODB_DB=cerberus
```

`.env` is gitignored — never commit secrets.

## 4. Dependencies

On the Ubuntu host (same environment that runs `serve.py`):

```bash
sudo pip3 install pymongo python-dotenv
# or use the project venv for API-only machines; root/system Python needs
# pymongo if serve.py runs under sudo system python3
```

Recommended for mixed BCC + deps:

```bash
sudo apt install -y python3-pymongo   # if packaged
# plus:
pip3 install --user python-dotenv
```

Or install into system site-packages used by `sudo python3`:

```bash
sudo pip3 install pymongo python-dotenv fastapi uvicorn pydantic chart-friendly-noop
sudo pip3 install -r requirements.txt
```

## 5. Verify

```bash
sudo python3 backend/serve.py eth0
# Look for: MongoDB Atlas: connected
```

Dashboard badge **Atlas ON**. Or:

```bash
curl -s http://127.0.0.1:8080/api/status | grep atlas
curl -s http://127.0.0.1:8080/api/atlas/events
```

In MongoDB Compass: connect with the same URI → database `cerberus` →
collections `events` and `snapshots`.

## 6. Thesis wording

> Detection and evaluation use local SQLite. MongoDB Atlas optionally mirrors
> operational events for remote observation; it is not on the packet path and
> is not required for experimental validity.

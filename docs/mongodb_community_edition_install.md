# MongoDB Community Edition on Fedora (doc-router)

This document walks through how we run **MongoDB Community Edition** and **mongot** (search / `$vectorSearch`) on **Fedora** for local development—same order you would follow on a new machine. It complements [INSTALL.local_devel.md](INSTALL.local_devel.md) and [env.md](env.md).

Official overview (Community install **with** Search on Linux):  
[Install MongoDB Community Edition — with Search](https://www.mongodb.com/docs/manual/administration/install-community/?linux-distribution=red-hat&linux-package=default&operating-system=linux&search-linux=with-search-linux).

**Components:**

| Piece | Role |
|--------|------|
| **`mongod`** | Data server on **27017** (unit name may be `mongod` or `mongod-community` depending on package). |
| **Replica set** | Required for mongot sync; we use a single-node set named **`rs0`**. |
| **mongot** | Separate process for `createSearchIndexes`, **`$vectorSearch`**, **`$search`** (MongoDB 8.x self-hosted + community mongot). Listens on **gRPC** (we use **27028** below). |

App connection string:

```text
mongodb://localhost:27017/?directConnection=true
```

`directConnection=true` avoids the driver discovering extra replica-set hosts when only one node exists.

---

## Install MongoDB on Fedora

MongoDB publishes RPM repos for RHEL-family systems; Fedora usually works with the [Red Hat install tutorial](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-redhat/). Add a repo file for the **major version** you want (example **8.0**, **x86_64**):

```bash
sudo tee /etc/yum.repos.d/mongodb-org-8.0.repo <<'EOF'
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/8/mongodb-org/8.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-8.0.asc
EOF
```

Adjust **baseurl** for your **architecture** (`aarch64` URL variants exist on MongoDB’s site).

```bash
sudo dnf install -y mongodb-org mongodb-mongosh
```

If clients reach MongoDB from other hosts, open the port (local-only dev often skips this):

```bash
sudo firewall-cmd --permanent --add-port=27017/tcp
sudo firewall-cmd --reload
```

---

## Configure `mongod`: storage, network, replication, and mongot

Edit **`/etc/mongod.conf`** (exact path: `rpm -ql mongodb-org-server`).

You want:

- **`storage.dbPath`** (often `/var/lib/mongo`).
- **`net.bindIp`** / **`net.port`**.
- **`replication.replSetName`**: **`rs0`** (must match what you pass to `rs.initiate`).
- **`setParameter`** so `mongod` knows how to reach mongot over **gRPC** (match the `server.grpc.address` you set in mongot’s `config.yml`—see below; we use **localhost:27028**).

Example (combine with your existing `systemLog` / security settings as needed):

```yaml
storage:
  dbPath: /var/lib/mongo
  wiredTiger:
    engineConfig:
      cacheSizeGB: 2   # cap WiredTiger RAM; tune for your machine

net:
  port: 27017
  bindIp: 127.0.0.1

replication:
  replSetName: "rs0"

setParameter:
  searchIndexManagementHostAndPort: localhost:27028
  mongotHost: localhost:27028
  skipAuthenticationToSearchIndexManagementServer: false
  useGrpcForSearch: true

systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true
```

**WiredTiger `cacheSizeGB`** is the main knob for **limiting `mongod` RAM** before you reach for systemd caps.

Restart `mongod` after editing:

```bash
sudo systemctl restart mongod
```

---

## Initialize the replica set

`mongot` expects a replica set. After `mongod` is running:

```bash
mongosh "mongodb://localhost:27017" --eval "rs.initiate({_id:'rs0',members:[{_id:0,host:'localhost:27017'}]})"
```

Wait until **`rs.status()`** shows your member as **PRIMARY**.

---

## Create the mongot database user

Mongot connects to `mongod` as a dedicated user (we use **`mongotUser`**) with the **`searchCoordinator`** role. In **`mongosh`**:

```javascript
use admin
db.createUser({
  user: "mongotUser",
  pwd: "<strong-password>",
  roles: [ "searchCoordinator" ]
})
```

Store the password in a **file** readable only by the account that runs mongot (see next section)—**do not** commit real passwords to the repo.

---

## Install mongot from the community tarball

Download the **mongot community** tarball for Linux from MongoDB (version in the URL changes; check [Search in Community](https://www.mongodb.com/try/download/search-in-community) for the current release):

```text
https://downloads.mongodb.org/mongodb-search-community/<version>/mongot_community_<version>_linux_x86_64.tgz
```

Example layout after unpacking under a fixed directory (we use **`/var/lib/mongot-community`**):

```text
/var/lib/mongot-community/
  bin/          # optional helper binaries
  lib/
  mongot        # main executable
  config.default.yml
  config.yml    # your edits
  README.md
  VERSION.txt
  mongot.example.logrotate
```

Unpack as the user that will run the service (below we use a normal user; production might use a dedicated system account).

---

## Mongot `config.yml` and password file

Create **`config.yml`** next to the `mongot` binary (paths are examples—keep them consistent on your host):

```yaml
syncSource:
  replicaSet:
    hostAndPort: "localhost:27017"
    username: mongotUser
    passwordFile: "/var/lib/mongot-community/passwordFile"
    tls: false

storage:
  dataPath: "/var/lib/mongot"

server:
  grpc:
    address: "localhost:27028"
    tls:
      mode: "disabled"

metrics:
  enabled: true
  address: "localhost:9946"

logging:
  verbosity: INFO
```

- **`passwordFile`**: single line, the password for **`mongotUser`**. Restrict permissions: `chmod 600 passwordFile`.
- **`storage.dataPath`**: on-disk Lucene / mongot state (large churn during heavy indexing).
- **`server.grpc.address`**: must align with **`setParameter.mongotHost`** / **`searchIndexManagementHostAndPort`** in **`mongod.conf`**.

Optional blocks in upstream samples (for example **embedding** / Voyage) are not required for basic doc-router KB search; leave them commented unless you use them.

Start mongot **once** from the install directory to verify config (optional debug flag—see **systemd** below for production-style invocation):

```bash
cd /var/lib/mongot-community
./mongot --config config.yml --internalListAllIndexesForTesting=true
```

Use **`--internalListAllIndexesForTesting=true`** only for troubleshooting; a normal **`ExecStart`** often omits it.

---

## Run mongot under systemd

Example unit: run as a specific user, working directory where **`config.yml`** lives, logs to **journald**:

```bash
sudo tee /etc/systemd/system/mongot-community.service <<'EOF'
[Unit]
Description=Mongot Community Service
After=network.target mongod.service

[Service]
Type=simple
User=andrei
WorkingDirectory=/var/lib/mongot-community
ExecStart=/var/lib/mongot-community/mongot --config config.yml
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Replace **`User=`** and paths with your deployment (a dedicated **`mongot`** system user is reasonable for shared servers). Ensure **`mongod`** is already up and PRIMARY before mongot starts (**`After=mongod.service`** helps ordering).

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mongot-community
sudo systemctl status mongot-community
```

---

## Limit CPU and RAM (systemd and JVM)

**mongod:** prefer **`wiredTiger.engineConfig.cacheSizeGB`** in **`mongod.conf`**. Optionally add **`MemoryMax=`** on the `mongod` unit as a hard ceiling.

**mongot (Java):** use **`systemctl edit mongot-community`** and set cgroup limits plus heap, for example:

```ini
[Service]
MemoryMax=4G
CPUQuota=200%
Environment=JAVA_TOOL_OPTIONS=-Xmx2g
```

Then `daemon-reload` and `restart`. Excessive initial-sync queues or **`OutOfMemoryError: Java heap space`** in mongot logs usually mean raising **`-Xmx`**, **`MemoryMax`**, or reducing parallel index churn.

```bash
systemctl show mongot-community -p MemoryMax -p CPUQuotaProportion
```

---

## doc-router application

In the project **`.env`**:

```bash
MONGODB_URI=mongodb://localhost:27017/?directConnection=true
```

Pytest uses logical DB names like **`pytest_gw*`** inside the same `mongod`; they are not separate servers.

---

## Upgrading

### MongoDB (`mongod`)

1. Back up ([Backup](#backup-and-restore) below).
2. `sudo dnf upgrade mongodb-org '*'` (or your pinned packages).
3. `sudo systemctl restart mongod`, confirm **`rs.status()`**, then restart mongot.

### mongot (tarball)

Check the running build:

```bash
cat /var/lib/mongot-community/VERSION.txt
```

Compare with the current release on [Search in Community](https://www.mongodb.com/try/download/search-in-community). Upgrade by **replacing binaries** while keeping **`config.yml`**, **`passwordFile`**, and **`storage.dataPath`** (e.g. `/var/lib/mongot`):

```bash
sudo systemctl stop mongot-community

curl -L -o /tmp/mongot-new.tgz \
  'https://downloads.mongodb.org/mongodb-search-community/0.64.0/mongot_community_0.64.0_linux_x86_64.tgz'
tar -xzf /tmp/mongot-new.tgz -C /tmp

cp -r /tmp/mongot_community_0.64.0_linux_x86_64/bin /var/lib/mongot-community/
cp -r /tmp/mongot_community_0.64.0_linux_x86_64/lib /var/lib/mongot-community/
cp /tmp/mongot_community_0.64.0_linux_x86_64/mongot /var/lib/mongot-community/
cp /tmp/mongot_community_0.64.0_linux_x86_64/VERSION.txt /var/lib/mongot-community/

sudo systemctl start mongot-community
```

Adjust paths and version numbers to match the tarball you downloaded.

---

## Logs and what to watch for

| Source | Command |
|--------|--------|
| **mongod** | `/var/log/mongodb/mongod.log` if configured, and/or `journalctl -u mongod` |
| **mongot** | `journalctl -u mongot-community` (follow: `-f`, only new lines: `-f -n 0` or `--since "now"`) |

Mongot may also write diagnostics under **`storage.dataPath`** (e.g. FTDC under a subdirectory—see mongot startup logs).

**Usually normal**

- **`Enqueueing initial sync` / `Queued initial syncs`**: index builds after `createSearchIndexes`.
- After **dropping** a collection/database: **`Collection was dropped`**, steady-state shutdown, Lucene **drop**—mongot releasing indexes for that namespace.

**Worth attention**

| Symptom | Likely cause | What to do |
|---------|----------------|------------|
| **`java.lang.OutOfMemoryError: Java heap space`** | Heap too small or too many indexes syncing | Increase **`-Xmx`**, **`MemoryMax`**, lighten load |
| **`No index in catalog` (WARN)** | Query before mongot registered the index | Short race; app retries; if persistent, check index creation and mongot health |
| Repeated failures right after upgrades | Config / port mismatch | Align **`mongod.conf`** `setParameter` with **`config.yml`** `server.grpc.address` |

---

## Backup and restore

**Logical backup:**

```bash
mongodump --uri="mongodb://localhost:27017/?directConnection=true" --db=yourdb --out=/backup/mongodump-$(date +%F)
mongorestore --uri="mongodb://localhost:27017/?directConnection=true" /backup/mongodump-YYYY-MM-DD/yourdb
```

**Project scripts:** `packages/python/analytiq_data/migrations/` (**MIGRATIONS.md**, **`backup_db.py`**) for URI/database copies in line with this repo.

For **mongot**, backing up **`storage.dataPath`** (while mongot is stopped or using procedures consistent with MongoDB guidance) preserves on-disk index state; often **`mongodump` of the data** plus rebuilding indexes is enough for dev—match your recovery requirements.

---

## Cleanup: databases, indexes, and mongot

**Drop a database** (mongot sees drops via replication and tears down search indexes for those namespaces):

```javascript
use yourdb
db.dropDatabase()
```

**Drop search indexes only:** use **`dropSearchIndexes`** (or current equivalent) for your server version; mongot stops maintaining those definitions.

**Leftover pytest DBs** (`pytest_gw0`, …): `show dbs`, then `use pytest_gwN` / `db.dropDatabase()`.

**Mongot disk:** after heavy use, **`storage.dataPath`** may not shrink immediately. Only remove that tree on a **dev** box with mongot stopped and after you understand the data loss risk; on production follow MongoDB procedures.

---

## Quick health checklist

- [ ] `mongosh "mongodb://localhost:27017/?directConnection=true"` connects.
- [ ] `rs.status()` → PRIMARY.
- [ ] `mongod.conf` **`setParameter`** ports match mongot **`config.yml`** gRPC address.
- [ ] `systemctl is-active mongod mongot-community` → `active`.
- [ ] `journalctl -u mongot-community -n 50` shows no repeated OOM after a smoke test (`createSearchIndexes` + small **`$vectorSearch`**, or the repo’s mongot integration test).

---

## References

- [MongoDB: Install Community with Search (Red Hat)](https://www.mongodb.com/docs/manual/administration/install-community/?linux-distribution=red-hat&linux-package=default&operating-system=linux&search-linux=with-search-linux)
- [MongoDB: Install on Red Hat / CentOS](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-redhat/)
- [MongoDB: mongod configuration](https://www.mongodb.com/docs/manual/reference/configuration-options/)
- [Search in Community (downloads)](https://www.mongodb.com/try/download/search-in-community)
- Project: [INSTALL.local_devel.md](INSTALL.local_devel.md), [env.md](env.md), Docker alternative: `deploy/compose/docker-compose.embedded.yml` (Atlas Local image with mongot).

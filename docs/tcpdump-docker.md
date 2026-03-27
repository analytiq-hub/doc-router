# tcpdump in Docker Compose Backend Container

## 1. Install tcpdump

```bash
docker compose -f deploy/compose/docker-compose.yml exec backend sh -c "apt-get update && apt-get install -y tcpdump"
```

## 2. Run and save to a .cap file

```bash
docker compose -f deploy/compose/docker-compose.yml exec backend \
  tcpdump -i any -s 0 'tcp port 8000' -w /tmp/capture.cap
```

Stop it with `Ctrl+C` when you've captured enough traffic.

## 3. Retrieve the file from the container

First get the container ID:
```bash
docker compose -f deploy/compose/docker-compose.yml ps -q backend
```

Then copy out the file:
```bash
docker cp <container_id>:/tmp/capture.cap ./capture.cap
```

Or in one step:
```bash
docker cp $(docker compose -f deploy/compose/docker-compose.yml ps -q backend):/tmp/capture.cap ./capture.cap
```

## 4. Inspect headers only

Open in Wireshark for a GUI view, or inspect with tcpdump locally:
```bash
tcpdump -r capture.cap -A 'tcp port 8000' | grep -E '^(GET|POST|PUT|DELETE|HTTP|Host:|Content-Type:|Authorization:|>)'
```

For just request/response lines:
```bash
tcpdump -r capture.cap -A | grep -E '(GET|POST|PUT|DELETE|PATCH) |HTTP/[0-9]'
```

#! /usr/bin/env python3

import argparse
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from pymongo import MongoClient

# Local forward port. Destination MongoDB in backup_db.sh is localhost:27017.
DEFAULT_SSH_LOCAL_PORT = 27018
SSH_READY_TIMEOUT_S = 20

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

def _mongo_endpoint(uri: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "mongodb":
        raise ValueError(f"Expected a mongodb:// URI, got '{parsed.scheme or '(none)'}'")
    if "," in parsed.netloc:
        raise ValueError("SSH tunnel supports a single host in the MongoDB URI")
    return parsed.hostname or "localhost", parsed.port or 27017


def _uri_on_local_port(uri: str, local_port: int) -> str:
    """Point a mongodb:// URI at the local tunnel port and force a direct connection."""
    parsed = urllib.parse.urlparse(uri)
    auth = ""
    if parsed.username is not None:
        auth = urllib.parse.quote(parsed.username, safe="")
        if parsed.password is not None:
            auth += ":" + urllib.parse.quote(parsed.password, safe="")
        auth += "@"
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key.lower() == "directconnection" for key, _ in query):
        query.append(("directConnection", "true"))
    return urllib.parse.urlunparse((
        parsed.scheme,
        f"{auth}127.0.0.1:{local_port}",
        parsed.path,
        parsed.params,
        urllib.parse.urlencode(query),
        parsed.fragment,
    ))


def _is_local_host(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "::1")


class SshTunnel:
    """Local port forward: 127.0.0.1:local_port -> remote_host:remote_port via ssh."""

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str,
        ssh_key: str,
        remote_host: str,
        remote_port: int,
        local_port: int,
    ) -> None:
        if shutil.which("ssh") is None:
            raise RuntimeError("ssh is not installed or not on PATH")

        key = Path(ssh_key).expanduser()
        if not key.is_file():
            raise FileNotFoundError(f"SSH key not found: {key}")

        self.local_port = local_port
        self._proc = subprocess.Popen(
            [
                "ssh",
                "-i", str(key),
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=15",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "IdentitiesOnly=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "StrictHostKeyChecking=accept-new",
                "-N",
                "-L", f"127.0.0.1:{local_port}:{remote_host}:{remote_port}",
                f"{ssh_user}@{ssh_host}",
            ],
        )
        try:
            self._wait_ready()
        except BaseException:
            self.close()
            raise

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + SSH_READY_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"SSH tunnel exited before it was ready (status {self._proc.returncode})"
                )
            try:
                with socket.create_connection(("127.0.0.1", self.local_port), timeout=0.3):
                    return
            except OSError:
                time.sleep(0.1)
        raise TimeoutError(
            f"SSH tunnel on 127.0.0.1:{self.local_port} was not ready within {SSH_READY_TIMEOUT_S}s"
        )

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description='Backup MongoDB database to another database.')
    parser.add_argument('--src-uri', required=True, help='Source MongoDB connection URI')
    parser.add_argument('--dest-uri', help='Destination MongoDB connection URI (defaults to source URI if not specified)')
    parser.add_argument('--src', required=True, help='Source database name')
    parser.add_argument('--dest', required=True, help='Destination database name')
    parser.add_argument('-f', '--force', action='store_true', help='Force drop the target database before backup')
    parser.add_argument('--batch-size', type=int, default=1000, help='Number of documents per insert batch (default: 1000)')
    parser.add_argument('--ssh-host', help='Reach --src-uri through an SSH tunnel to this host')
    parser.add_argument('--ssh-user', default='ubuntu', help='SSH user (default: ubuntu)')
    parser.add_argument('--ssh-key', help='SSH private key path (required with --ssh-host)')
    parser.add_argument(
        '--ssh-local-port',
        type=int,
        default=DEFAULT_SSH_LOCAL_PORT,
        help=f'Local port for the SSH tunnel (default: {DEFAULT_SSH_LOCAL_PORT})',
    )

    args = parser.parse_args()

    if args.ssh_host and not args.ssh_key:
        parser.error('--ssh-key is required when --ssh-host is set')

    # Use source URI as destination URI if not specified
    dest_uri = args.dest_uri or args.src_uri
    src_uri = args.src_uri

    if args.src == args.dest and not args.ssh_host and src_uri == dest_uri:
        print("Error: Source and destination databases must be different when using the same MongoDB instance")
        sys.exit(1)

    tunnel = None
    try:
        if args.ssh_host:
            remote_host, remote_port = _mongo_endpoint(src_uri)
            dest_host, dest_port = _mongo_endpoint(dest_uri)
            if args.ssh_local_port == dest_port and _is_local_host(dest_host):
                print(
                    f"Error: SSH local port {args.ssh_local_port} is the same as the destination "
                    f"MongoDB port. Pass a different --ssh-local-port."
                )
                sys.exit(1)
            print(
                f"Opening SSH tunnel {args.ssh_user}@{args.ssh_host}: "
                f"127.0.0.1:{args.ssh_local_port} -> {remote_host}:{remote_port}"
            )
            tunnel = SshTunnel(
                args.ssh_host,
                args.ssh_user,
                args.ssh_key,
                remote_host,
                remote_port,
                args.ssh_local_port,
            )
            src_uri = _uri_on_local_port(args.src_uri, tunnel.local_port)

        backup_database(src_uri, dest_uri, args.src, args.dest, args.force, args.batch_size)
    finally:
        if tunnel is not None:
            tunnel.close()

if __name__ == "__main__":
    main()

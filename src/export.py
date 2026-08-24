import json

from .vault import BACKUP_MAGIC, read_container, write_container


def write_backup(path, data, password):
    write_container(path, BACKUP_MAGIC, password, json.dumps(data).encode("utf-8"))


def read_backup(path, password):
    payload = read_container(path, BACKUP_MAGIC, password)
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict) or "accounts" not in data:
        raise ValueError("Invalid backup content")
    return data


def merge_accounts(current, incoming):
    seen = {(a.get("secret"), a.get("label")) for a in current}
    added = 0
    for account in incoming:
        key = (account.get("secret"), account.get("label"))
        if key in seen:
            continue
        current.append(account)
        seen.add(key)
        added += 1
    return added

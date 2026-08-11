import uuid

NAMESPACE = uuid.UUID("c0ffee00-0000-0000-0000-c0ffee000000")


def stable_id(source: str, chunk_index: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{source}::{chunk_index}"))


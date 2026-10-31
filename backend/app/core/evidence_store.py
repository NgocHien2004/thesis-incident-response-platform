import hashlib
import os
import re
import uuid
from pathlib import Path

CHUNK = 1024 * 1024
MAX_MB = int(os.getenv("EVIDENCE_MAX_MB", "20"))
MAX_BYTES = MAX_MB * 1024 * 1024


class TooLarge(Exception):
    pass


def storage_root() -> Path:
    env = os.getenv("EVIDENCE_STORAGE_DIR")
    base = Path(env) if env else Path(__file__).resolve().parents[2] / "evidence_store"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def safe_filename(name: str | None) -> str:
    """Chỉ giữ tên tệp, bỏ đường dẫn và ký tự điều khiển; chỉ dùng để hiển thị, không dùng để lưu."""
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().strip(".")
    if not name:
        return "tep-khong-ten"
    if len(name) > 255:
        stem, dot, ext = name.rpartition(".")
        name = (stem[:240] + dot + ext[:14]) if dot and len(ext) <= 14 else name[:255]
    return name


def new_key(incident_id: int) -> str:
    return f"{incident_id}/{uuid.uuid4().hex}"


def path_for(key: str) -> Path:
    root = storage_root()
    path = (root / key).resolve()
    if root not in path.parents:
        raise ValueError("Khóa lưu trữ không hợp lệ")
    return path


def save_stream(fileobj, key: str, max_bytes: int = MAX_BYTES):
    """Ghi luồng vào kho và tính SHA-256 trên đúng các byte đã ghi. Trả về (sha256, số byte)."""
    path = path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with open(path, "xb") as out:
            while True:
                chunk = fileobj.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise TooLarge()
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        delete_quietly(key)
        raise
    try:
        os.chmod(path, 0o444)
    except OSError:
        pass
    return digest.hexdigest(), size


def hash_file(key: str):
    """Băm lại tệp đang lưu. Trả về (sha256, số byte), hoặc None nếu tệp không còn."""
    path = path_for(key)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def delete_quietly(key: str):
    try:
        path = path_for(key)
        if path.exists():
            try:
                os.chmod(path, 0o666)
            except OSError:
                pass
            path.unlink()
    except (OSError, ValueError):
        pass

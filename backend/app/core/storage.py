import os

_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "upload_store")
UPLOAD_STORAGE_DIR = os.getenv("UPLOAD_STORAGE_DIR", _DEFAULT)

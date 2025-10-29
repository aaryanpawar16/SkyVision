from fastapi import Depends
from .db import init_pool

def get_ready():
    # Ensure DB pool is initialized for requests
    init_pool()
    return True

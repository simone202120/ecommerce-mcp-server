from ecommerce_mcp.config import Settings
from ecommerce_mcp.infra.db import read_only_pool


def test_read_only_pool_forces_read_only_time_limited_sessions() -> None:
    settings = Settings(_env_file=None, db_statement_timeout_ms=1234, db_pool_size=3)
    pool = read_only_pool(settings)
    options = pool.kwargs["options"]
    assert "default_transaction_read_only=on" in options
    assert "statement_timeout=1234" in options
    assert pool.max_size == 3
    assert pool.closed

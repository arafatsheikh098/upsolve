import pytest

from app.config import Settings


def test_production_refuses_dev_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(env="production", jwt_secret="dev-only-change-me")
    assert Settings(env="production", jwt_secret="x" * 40).env == "production"

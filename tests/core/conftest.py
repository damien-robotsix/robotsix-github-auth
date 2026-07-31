"""Shared test fixtures for robotsix-github-auth tests."""

from __future__ import annotations

import pytest

# Test RSA private key (generated for testing only — NOT a real secret)
TEST_PRIVATE_KEY: str = """-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCbYUzaOiBidZG6
7Mfgfe+Kb2zO7vjzLRk26HCcgsGZPTW3qP4ZuKWwMpp5d+GGtedW6FfojTzLhxNX
/TsWNXFdVRDtCfb1LakyzDg9Qf+LTE+1juKA85rOC8NJBQrdOlSz1Q4+SdKoqe6j
0q65c6QA0SbkL5Dxao7+2N4/WpCkHBfqFnClxbo2CEaipl1WEAwKTCZqgwei0x55
3zDaF8peH9mPN4Y1QbIjR7Avas6MNNgzyh1QVvn8i+lIooPK0sxBXcdOTrUSvZY4
kMq6s4N5du8q1nHFruf3N5KJdNO+zvvVqHHyANlpfkPLzAVEr0gc2Go9H5Vj6W2e
NC4FSBC9AgMBAAECggEAHx/PtPQJSie6VBr7k8KuQcj9nvr8F7wMLbVEX3mKvb8m
3D4H/k+AMwoD6vqCTMlxyHUcrNrj13IchBbX5+Q3K+avEAhbtXOaza/eQRkQDw9v
dRMk2IdTllwBV4ZgzX1Se75dDsmbXslBYgQBF2lsa/R5aaKEknNRpwd6h27FA/ZD
uFdJjnweEviJKakxVaoBI2IQ0jceByZEBkOtOhoE+7AMaZKUc1SKFXgclj9eH9/F
itIrHw+IPe310EC9Vmofkhwoc+KD1N9a08ZbY39nnK90g106+WGhbRIt248ts5a7
VdzToCyLdQcQOMMDYzdHMfYkxhDG2nsCUwfHM04rqQKBgQDO57NWSGKiX9bwVEd/
1y/f3X6gi4EPsG4l93aDB3ScSpfI+icTme/NWIiRB7FMMxQhQNxx/7Fc11Ip6iHJ
zjRU4KbgbBmEwFGGq7Tl4Pern472+g1ZfuE6j+KtPSf8FWL7IX+he6cSK4diKiiW
HgSViJjCrQamBWeRd0chwDc/WQKBgQDAP8AvxC+2ahpr1f7nCMNiN+yKJqKHCaDt
Uz9aNA7YsER/c3W5V6DdBpIh7pBtufIf0R/u7dz+p4ev3yhSxEcGjBWZz62Jr535
RKd0FLjzNrkhP3W8yra1lco5EDzEzybxTR6cXcHMFiiBd5wg1jQqGVRL2hx52mNT
Yh+Gmwv0BQKBgAqz1YT7DY8UogugcGpeeS19SZWIYc6r86anHEw+0HtdKGjO98J9
zfezQq0t1q/4XGwz7LNA5K3GvYtJfyHvNqnFTRyCuvcw84ahzyOs9WK9SCniWVpt
w7zBwJnxdeYGPS58VxvFR6ka80/SmnLZbqdFf5FiXdusn+TYZKeMR89RAoGAfaUs
pgtCY6XUvsWNYtGHYJnMLj4x2q+gTXsq3HlJerU5D1MWjZuHtuykdSjFm/D7HXA/
vpgW5xf2xirC39UH1m+Xbn8cm+/6/v6vsl4YwlvxgplHCawy3VqYX9MM5FO+z9Xn
O6rLDectcfAKSiu0zA7h2PEjyz+/yq9Gi2Kp3UECgYB6PrAlSXpaMCwxoAi0N2Ca
yBgbtePEfNSH5/2Ua9CknoWMWjneyv4Fy88zKc1J+uAyzzSizD39qQcH5HM3JKSY
5mA7rDBe/57RaNJLQtY/5RQZYqF3aTGYJlEVRaxavUDiotcz71UkomzWu1ErerZY
Y0yClTxGX5J6nwCXZD54XA==
-----END PRIVATE KEY-----"""

TEST_APP_ID: str = "123456"


@pytest.fixture
def private_key() -> str:
    """Return a test RSA private key (PEM format)."""
    return TEST_PRIVATE_KEY


@pytest.fixture
def app_id() -> str:
    """Return a test GitHub App ID."""
    return TEST_APP_ID

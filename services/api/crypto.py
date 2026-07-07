"""SEVER API — application-layer encryption for Plaid access tokens.

Tokens are encrypted with AWS KMS before storage (defense in depth on top
of database-level encryption). When SEVER_KMS_KEY_ID is unset (local dev
and CI), a reversible plaintext encoding is used and clearly marked.
"""

import base64
import os


def _kms():
    import boto3

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.client("kms", region_name=region)


def encrypt_token(plaintext: str) -> str:
    key_id = os.environ.get("SEVER_KMS_KEY_ID")
    if not key_id:
        return "plain:" + base64.b64encode(plaintext.encode()).decode()
    blob = _kms().encrypt(KeyId=key_id, Plaintext=plaintext.encode())["CiphertextBlob"]
    return "kms:" + base64.b64encode(blob).decode()


def decrypt_token(stored: str) -> str:
    if stored.startswith("plain:"):
        return base64.b64decode(stored[6:]).decode()
    if stored.startswith("kms:"):
        return _kms().decrypt(CiphertextBlob=base64.b64decode(stored[4:]))["Plaintext"].decode()
    raise ValueError("unrecognized token encoding")

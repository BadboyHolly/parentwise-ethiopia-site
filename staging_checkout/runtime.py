"""Synthetic CI entry point for the isolated staging API."""
from staging_checkout.app import from_environment

app = from_environment()

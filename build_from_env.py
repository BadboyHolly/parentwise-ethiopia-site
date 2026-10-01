import base64
import io
import os
import zipfile

count = int(os.environ["PW_PACKAGE_PARTS"])
payload = "".join(os.environ[f"PW_PACKAGE_{i:02d}"] for i in range(count))
archive = base64.b64decode(payload)

with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
    bundle.extractall(".")

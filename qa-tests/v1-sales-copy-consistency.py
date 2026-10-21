"""Copy-only acceptance for the isolated ParentWise V1 sales review; no deployment."""
from pathlib import Path
import hashlib, re

root=Path("index.html").read_bytes()
mirror=Path("public/index.html").read_bytes()
assert root==mirror, "Root and published mirror differ"
s=root.decode("utf-8")
assert len(s)>3_400_000
for text in ("የትዕዛዝ ቁጥር", "ሙሉ በሙሉ እንመልስልዎታለን", "30-DAY PRACTICE GUARANTEE"):
    assert text not in s, f"obsolete purchase copy: {text}"
for text in (
    "የ30 ቀን የተግባር እቅድ",
    "የክፍያ ሂሳብ ቁጥርና የሂሳብ ባለቤት",
    "የዝውውር ማጣቀሻ ቁጥርዎን",
    "አምስቱ የParentWise PDF ፋይሎች",
    "እውነተኛ ክፍያ አይፈጽሙ",
    'id="section-10"',
    'id="section-11"',
    'href="order.html"',
):
    assert text in s, f"Missing required flow copy: {text}"
for text in ("0912910693","1000223019327","10002230019327"):
    assert text not in s, "Live recipient number leaked"
assert s.count('id="section-10"')==1 and s.count('id="section-11"')==1
for section in ("section-01","section-02","section-03","section-04","section-05","section-06","section-07","section-08","section-09"):
    assert section in s, section
print("PASS: aligned purchase steps, verified-number requirement removed, refund promise removed")
print("PASS: main QA purchase link, eleven section IDs, public no-pay warnings, no real account numbers")
print("PASS: root/public copies byte-identical, sha256="+hashlib.sha256(root).hexdigest())

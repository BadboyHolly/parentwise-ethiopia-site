"""Phase 6 destructive checks ONLY on disposable local CI PostgreSQL."""
import os, json, hashlib, secrets, subprocess
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from fastapi.testclient import TestClient

assert os.environ.get("GITHUB_ACTIONS") == "true"
assert os.environ.get("APP_MODE") == "qa" and os.environ.get("PAYMENTS_ENABLED") == "false"
url = os.environ["DATABASE_URL"]
assert url == "postgresql+psycopg://qa_ci@localhost:5432/pw_qa_disposable"
engine = create_engine(url)
def passed(label): print("PASS Phase 6 PostgreSQL " + label,flush=True)
def snapshot(e):
    result = {}
    with e.connect() as c:
        names = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
        for name in names:
            rows = c.execute(text('SELECT row_to_json(t)::text FROM "'+name+'" t ORDER BY row_to_json(t)::text')).scalars().all()
            result[name] = {"rows":len(rows),"sha256":hashlib.sha256("\\n".join(rows).encode()).hexdigest()}
    return result

for table in ("qa_payment_events","qa_fulfillment_events"):
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM "+table)) > 0
    for verb in ("UPDATE","DELETE"):
        try:
            with engine.begin() as c:
                sql = "UPDATE "+table+" SET actor='tampered'" if verb=="UPDATE" else "DELETE FROM "+table
                c.execute(text(sql))
        except DBAPIError as exc:
            assert "append-only" in str(exc.orig)
        else: raise AssertionError(table+" "+verb+" unexpectedly allowed")
        passed(table+" rejects actual "+verb+" on migrated data")

for table, change in (("orders","amount_etb=1499"),("orders","currency='USD'"),
 ("qa_fulfillments","package_version='REAL-PRODUCT'"),
 ("qa_fulfillments","attempt_count=-1"),("qa_fulfillments","state='REAL_SENT'")):
    try:
        with engine.begin() as c: c.execute(text("UPDATE "+table+" SET "+change))
    except DBAPIError as exc: assert getattr(exc.orig,"sqlstate",None)=="23514"
    else: raise AssertionError("constraint not enforced: "+change)
    passed("database constraint "+change)

from api import main
key = secrets.token_urlsafe(32)
body = {"customer_name":"Phase Six Injected Failure","mobile":"0912345678","payment_method":"bank"}
before = snapshot(engine)
with engine.begin() as c:
    c.execute(text("""CREATE FUNCTION phase6_abort_insert() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN IF NEW.customer_name='Phase Six Injected Failure' THEN RAISE EXCEPTION 'synthetic commit failure'; END IF;
    RETURN NEW; END; $$"""))
    c.execute(text("CREATE TRIGGER phase6_abort BEFORE INSERT ON orders FOR EACH ROW EXECUTE FUNCTION phase6_abort_insert()"))
try:
    with TestClient(main.app,base_url="https://localhost:8443") as client:
        failed = client.post("/api/v1/orders",json=body,headers={"Idempotency-Key":key})
        assert failed.status_code==503 and "synthetic commit failure" not in failed.text
        assert snapshot(engine)==before
        passed("transaction failure returns sanitized 503 and rolls back order plus quota")
finally:
    with engine.begin() as c:
        c.execute(text("DROP TRIGGER phase6_abort ON orders"))
        c.execute(text("DROP FUNCTION phase6_abort_insert()"))
with TestClient(main.app,base_url="https://localhost:8443") as client:
    first=client.post("/api/v1/orders",json=body,headers={"Idempotency-Key":key})
    second=client.post("/api/v1/orders",json=body,headers={"Idempotency-Key":key})
    assert first.status_code==201 and first.json()==second.json()
    passed("retry after transaction failure creates exactly one recoverable order")
from concurrent.futures import ThreadPoolExecutor
race_key=secrets.token_urlsafe(32)
with TestClient(main.app,base_url="https://localhost:8443") as client:
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _: client.post("/api/v1/orders",json=body,headers={"Idempotency-Key":race_key}),range(4)))
    assert all(r.status_code==201 for r in responses)
    assert all(r.json()==responses[0].json() for r in responses)
    conflict=client.post("/api/v1/orders",json={**body,"payment_method":"telebirr"},headers={"Idempotency-Key":race_key})
    assert conflict.status_code==409
passed("PostgreSQL concurrent duplicate submissions produce one order; changed replay is rejected")
before=snapshot(engine)
subprocess.run(["alembic","upgrade","head"],check=True)
assert before==snapshot(engine)
passed("repeated Alembic upgrade preserves existing orders and histories")
container=os.environ["PG_CONTAINER"]
subprocess.run(["docker","exec",container,"createdb","-U","qa_ci","phase6_restore"],check=True)
dump=subprocess.run(["docker","exec",container,"pg_dump","-U","qa_ci","-d","pw_qa_disposable","-Fc"],capture_output=True,check=True).stdout
subprocess.run(["docker","exec","-i",container,"pg_restore","-U","qa_ci","-d","phase6_restore","--exit-on-error"],input=dump,check=True)
restored=create_engine(url.replace("/pw_qa_disposable","/phase6_restore"))
assert snapshot(restored)==before
passed("pg_dump and pg_restore reproduce every table row and audit event exactly")
with restored.connect() as c:
    assert c.scalar(text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('qa_payment_events_append_only','qa_fulfillment_events_append_only')"))==2
passed("restored database retains append-only audit triggers")
# An existing Phase 1 order must survive all later migrations.
subprocess.run(["docker","exec",container,"createdb","-U","qa_ci","phase6_legacy"],check=True)
legacy_url=url.replace("/pw_qa_disposable","/phase6_legacy")
legacy_env={**os.environ,"DATABASE_URL":legacy_url}
subprocess.run(["alembic","upgrade","20261009_01"],env=legacy_env,check=True)
legacy=create_engine(legacy_url)
with engine.connect() as c:
    row=dict(c.execute(text("SELECT * FROM orders WHERE status='PENDING_PAYMENT' LIMIT 1")).mappings().one())
columns=list(row)
with legacy.begin() as c:
    c.execute(text("INSERT INTO orders ("+",".join(columns)+") VALUES ("+",".join(":"+k for k in columns)+")"),row)
subprocess.run(["alembic","upgrade","head"],env=legacy_env,check=True)
with legacy.connect() as c: assert dict(c.execute(text("SELECT * FROM orders")).mappings().one())==row
passed("Phase 1 populated database migrates safely to current head")
Path("../qa-test-evidence").mkdir(exist_ok=True)
Path("../qa-test-evidence/phase6-database-manifest.json").write_text(json.dumps(before,indent=2))
print("PHASE 6 DATABASE RESILIENCE BACKUP AND MIGRATION ACCEPTANCE PASS",flush=True)

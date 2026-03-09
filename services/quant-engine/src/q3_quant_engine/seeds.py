import subprocess
import uuid

from q3_quant_engine.db.session import SessionLocal
from q3_shared_models.entities import Membership, MembershipRole, Tenant, User

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

SEED_USERS = [
    {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000010"),
        "email": "demo@q3.dev",
        "full_name": "Demo User",
        "password": "Q3demo!2026",
        "membership_id": uuid.UUID("00000000-0000-0000-0000-000000000202"),
    },
]


def _hash_password(password: str) -> str:
    """Hash password using Node.js bcryptjs (same lib the API uses)."""
    result = subprocess.run(
        ["node", "-e", f"require('bcryptjs').hash('{password}',10).then(h=>process.stdout.write(h))"],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[4] / "apps" / "api"),
        check=True,
    )
    return result.stdout


def main() -> None:
    with SessionLocal() as session:
        tenant = session.get(Tenant, TENANT_ID)
        if tenant is None:
            tenant = Tenant(id=TENANT_ID, name="Q3 Demo Tenant")
            session.add(tenant)
            session.flush()

        for u in SEED_USERS:
            user = session.get(User, u["id"])
            if user is None:
                user = User(
                    id=u["id"],
                    email=u["email"],
                    full_name=u["full_name"],
                    password_hash=_hash_password(u["password"]),
                )
                session.add(user)
                session.flush()

            membership = session.get(Membership, u["membership_id"])
            if membership is None:
                membership = Membership(
                    id=u["membership_id"],
                    tenant_id=TENANT_ID,
                    user_id=u["id"],
                    role=MembershipRole.owner,
                )
                session.add(membership)

        session.commit()

    print("[q3-seed] done")


if __name__ == "__main__":
    main()

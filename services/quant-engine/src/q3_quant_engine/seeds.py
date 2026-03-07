import uuid

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.models.entities import Membership, MembershipRole, Tenant, User


def main() -> None:
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000101")
    membership_id = uuid.UUID("00000000-0000-0000-0000-000000000201")

    with SessionLocal() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            tenant = Tenant(id=tenant_id, name="Q3 Demo Tenant")
            session.add(tenant)

        user = session.get(User, user_id)
        if user is None:
            user = User(id=user_id, email="demo@q3.local", full_name="Demo User")
            session.add(user)

        session.commit()

        membership = session.get(Membership, membership_id)
        if membership is None:
            membership = Membership(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role=MembershipRole.owner,
            )
            session.add(membership)

        session.commit()

    print("[q3-seed] done")


if __name__ == "__main__":
    main()

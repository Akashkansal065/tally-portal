import asyncio
from app.core.database import AsyncSessionLocal
from app.models.company import Company
from app.models.user import User, Role
from sqlalchemy.future import select

async def fix():
    async with AsyncSessionLocal() as s:
        # Get Admin Role
        role_q = await s.execute(select(Role).where(Role.name == "Admin"))
        admin_role = role_q.scalars().first()
        if not admin_role:
            print("No Admin role found! Seed might be incomplete.")
            return
            
        print(f"Found Admin Role ID: {admin_role.role_id}")
        
        # Get Admin User
        user_q = await s.execute(select(User).where(User.email == "admin_test@test.com"))
        user = user_q.scalars().first()
        if user:
            print(f"Updating user {user.email} from Role ID {user.role_id} to {admin_role.role_id}")
            user.role_id = admin_role.role_id
            await s.commit()
            print("User role updated successfully.")
        else:
            print("admin_test@test.com user not found in database.")

if __name__ == "__main__":
    asyncio.run(fix())

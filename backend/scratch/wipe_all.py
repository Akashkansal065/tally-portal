import asyncio
from sqlalchemy import text
from app.core.database import engine

async def wipe_all_companies_and_users():
    print("Connecting to database...")
    async with engine.begin() as conn:
        print("Disabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # Truncate all company and user data tables
        print("Wiping all company, user, session, and permission override records...")
        await conn.execute(text("TRUNCATE TABLE companies;"))
        await conn.execute(text("TRUNCATE TABLE users;"))
        await conn.execute(text("TRUNCATE TABLE user_company_access;"))
        await conn.execute(text("TRUNCATE TABLE user_sessions;"))
        await conn.execute(text("TRUNCATE TABLE user_permission_overrides;"))
        
        print("Enabling foreign key checks...")
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    print("All companies and users have been deleted successfully!")

if __name__ == "__main__":
    asyncio.run(wipe_all_companies_and_users())

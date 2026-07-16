import sys
from sqlalchemy import create_engine, text

def run_setup():
    # Try different MySQL root connection guesses to create databases and grant permissions
    root_urls = [
        "mysql+pymysql://root:rootpassword@localhost:3306",
        "mysql+pymysql://root:@localhost:3306",
        "mysql+pymysql://root:rootpassword@127.0.0.1:3306",
        "mysql+pymysql://root:@127.0.0.1:3306"
    ]
    
    success = False
    for url in root_urls:
        print(f"Trying connection to root MySQL at {url}...")
        try:
            engine = create_engine(url)
            with engine.connect() as conn:
                print("Connected! Creating databases...")
                conn.execute(text("CREATE DATABASE IF NOT EXISTS tally_portal;"))
                conn.execute(text("CREATE DATABASE IF NOT EXISTS tally_sync;"))
                
                print("Granting privileges to mytally_user...")
                try:
                    conn.execute(text("GRANT ALL PRIVILEGES ON tally_portal.* TO 'mytally_user'@'%';"))
                    conn.execute(text("GRANT ALL PRIVILEGES ON tally_sync.* TO 'mytally_user'@'%';"))
                    conn.execute(text("FLUSH PRIVILEGES;"))
                    print("Privileges granted successfully!")
                except Exception as grant_err:
                    print(f"Warning: Could not grant privileges (user may already have them or host mismatch): {grant_err}")
                
                success = True
                break
        except Exception as e:
            print(f"Connection failed: {e}\n")
            
    if not success:
        print("Error: Could not connect as root to MySQL. Please create the databases manually using:")
        print("CREATE DATABASE IF NOT EXISTS tally_portal;")
        print("CREATE DATABASE IF NOT EXISTS tally_sync;")
        print("GRANT ALL PRIVILEGES ON tally_portal.* TO 'mytally_user'@'%';")
        print("GRANT ALL PRIVILEGES ON tally_sync.* TO 'mytally_user'@'%';")
        sys.exit(1)

if __name__ == "__main__":
    run_setup()

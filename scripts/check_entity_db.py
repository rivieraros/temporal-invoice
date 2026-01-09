"""Quick database check script."""
import sqlite3

conn = sqlite3.connect('ap_automation.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cursor.fetchall()])

# Count entity resolver records
cursor.execute("SELECT COUNT(*) FROM entity_profile")
print(f"Entity profiles: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM entity_routing_key")
print(f"Routing keys: {cursor.fetchone()[0]}")

# Sample data
print("\nEntity profiles:")
cursor.execute("SELECT entity_code, entity_name, entity_id FROM entity_profile")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} ({row[2][:20]}...)")

print("\nRouting keys:")
cursor.execute("SELECT key_type, key_value, entity_id, confidence FROM entity_routing_key")
for row in cursor.fetchall():
    print(f"  [{row[0]}] {row[1]} -> {row[2][:20]}... ({row[3]})")

conn.close()

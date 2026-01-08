""" try camera support 
web agent 
google maps and location of mate and contacts """

import sqlite3
from datetime import datetime

conn = sqlite3.connect('tars.db')
conn.row_factory = sqlite3.Row

# Get conversations grouped by date
cursor = conn.execute("""
    SELECT 
        DATE(timestamp) as date,
        COUNT(*) as count,
        GROUP_CONCAT(DISTINCT medium) as mediums
    FROM conversations
    GROUP BY DATE(timestamp)
    ORDER BY date DESC
    LIMIT 30
""")

print("\nConversations by Date:")
print("=" * 60)
for row in cursor.fetchall():
    print(f"{row['date']}: {row['count']} conversations ({row['mediums']})")

conn.close()
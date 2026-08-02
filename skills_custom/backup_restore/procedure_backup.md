# Backup & Restore CLARA Knowledge

Kiểm tra DB: `sqlite3 data/clara.db "SELECT COUNT(*) FROM procedures;"`

## Backup
```bash
python3 -c "from memory import ClarasMemory; ClarasMemory('data/clara.db').export_knowledge('backups/knowledge_$(date +%Y%m%d).json')"
```

## Restore from backup
```bash
cp data/clara.db data/clara.db.bak
python3 -c "
import json
from memory import ClarasMemory
m=ClarasMemory('data/clara.db')
backup=json.load(open('backups/knowledge_YYYYMMDD.json'))
for row in backup['semantics']:
    m.add_fact(row['key'], row['value'], source='restore')
for row in backup['procedures']:
    m.add_procedure(row['name'], row['description'], row['steps'], row['success_rate'])
"
```

## Verify
```sql
sqlite3 data/clara.db "SELECT name,success_rate,times_used FROM procedures ORDER BY success_rate DESC;"
```

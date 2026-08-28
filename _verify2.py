import main
from self_upgrade import apply_patch, rollback as up_rollback, list_backups

a = main.ClarasAGI(force_micro=True)
src = open('tools.py', encoding='utf-8').read()
first_line = src.splitlines()[0]
new_first_line = '# CLARA tool dispatch (self-upgraded test)'
res = apply_patch('tools.py', first_line, new_first_line, is_core=False, agi=a)
print('APPLY ok=', res.get('ok'))
print('git=', res.get('git'))
print('backup=', res.get('backup'))
print('backup exists=', __import__('os').path.exists(res.get('backup','')))
print('first line now:', open('tools.py', encoding='utf-8').readline().strip())

# Rollback
rb = up_rollback('tools.py')
print('ROLLBACK:', rb)
print('first line after rollback:', open('tools.py', encoding='utf-8').readline().strip())

# Negative test: patch gây lỗi cú pháp phải tự rollback
bad = apply_patch('tools.py', first_line, 'def (broken syntax (((', is_core=False, agi=a)
print('BAD patch ok=', bad.get('ok'), '| error=', bad.get('error'))
print('first line after bad rollback:', open('tools.py', encoding='utf-8').readline().strip())

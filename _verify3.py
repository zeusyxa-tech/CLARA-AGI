import main
from self_upgrade import apply_patch, rollback as up_rollback

a = main.ClarasAGI(force_micro=True)
src = open('tools.py', encoding='utf-8').read()
lines = src.splitlines()
# Chọn một dòng comment/blank an toàn ở cuối file để thay thành comment khác (syntax vẫn OK)
target_line = None
for i in range(len(lines)-1, 0, -1):
    ln = lines[i]
    if ln.strip().startswith('#') or ln.strip() == '':
        target_line = ln
        break
print('TARGET LINE repr:', repr(target_line))
new_line = target_line.rstrip() + '  # self-upgraded marker'
res = apply_patch('tools.py', target_line, new_line, is_core=False, agi=a)
print('APPLY ok=', res.get('ok'), '| error=', res.get('error'))
print('git=', res.get('git'))
if res.get('ok'):
    rb = up_rollback('tools.py')
    print('ROLLBACK:', rb)

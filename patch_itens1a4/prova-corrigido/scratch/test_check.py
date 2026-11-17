import sys
sys.path.insert(0, r'D:\PROVA lenguaje')
from provac.check import is_atomic, is_ptr, base, declare, SCALARS

# Simulate what happens during check
T = ['own', 'atomic', 'u32']
print(f'T: {T}')
print(f'is_atomic(T): {is_atomic(T)}')
print(f'is_ptr(T): {is_ptr(T)}')
print(f'T in SCALARS: {T in SCALARS}')
print(f'T not in SCALARS and not is_ptr(T) and not is_atomic(T): {T not in SCALARS and not is_ptr(T) and not is_atomic(T)}')

# Test declare
cx = type('Cx', (), {'types': {}, 'mut': set(), 'slice_names': set(), 'data': {}, 'obs': [], 'fn': None, 'sigs': {}})
try:
    declare(cx, 'x', T, False)
    print(f'declare succeeded! cx.types: {cx.types}')
except Exception as e:
    print(f'declare failed: {e}')
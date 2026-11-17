import sys
sys.path.insert(0, r'D:\PROVA lenguaje')
from provac.check import PTR_REGIONS, ATOMIC_ORDERS

# Test the condition
T = ['own', 'atomic', 'u32']
print(f'isinstance(T, list) and T[0] == "ptr": {isinstance(T, list) and T[0] == "ptr"}')
print(f'isinstance(T, list) and T[0] == "own": {isinstance(T, list) and T[0] == "own"}')
print(f'len(T) >= 3: {len(T) >= 3}')
print(f'T[2] in PTR_REGIONS: {T[2] in PTR_REGIONS}')
print(f'T[2] in ATOMIC_ORDERS: {T[2] in ATOMIC_ORDERS}')
print(f'len(T) >= 3 and T[2] in PTR_REGIONS: {len(T) >= 3 and T[2] in PTR_REGIONS}')
print(f'len(T) >= 3 and T[2] in ATOMIC_ORDERS: {len(T) >= 3 and T[2] in ATOMIC_ORDERS}')
print(f'len(T) >= 3 and (T[2] in PTR_REGIONS or T[2] in ATOMIC_ORDERS): {len(T) >= 3 and (T[2] in PTR_REGIONS or T[2] in ATOMIC_ORDERS)}')
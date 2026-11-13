import sys
sys.path.insert(0, r'D:\PROVA linguagem')
import importlib
import provac.check
importlib.reload(provac.check)

# Test is_atomic
T = ['own', 'atomic', 'u32']
print(f'is_atomic: {provac.check.is_atomic(T)}')

# Now test the full check
import provac
importlib.reload(provac)
from provac import prova

try:
    data, compiled, results = prova.analyse('D:/PROVA linguagem/examples/atomic_test.prova')
    print('Success! analyse worked')
    print(f'compiled={compiled}')
    print(f'results={results}')
except Exception as e:
    print(f'Error during analyse: {e}')
    import traceback
    traceback.print_exc()
import sys
sys.path.insert(0, r'D:\PROVA lenguaje')
import prova

try:
    data, compiled, results = prova.analyse('D:/PROVA linguagem/examples/atomic_test.prova')
    print(f'Success! compiled={compiled}')
    print(f'results={results}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
import sys
sys.path.insert(0, 'D:/PROVA linguagem')
import prova

# Write a test file with ptr type
with open('test_ptr_mmap.prova', 'w') as f:
    f.write('(fn test_mmap (params (n usize) (buf (ptr mmio))) (returns unit) (pre (<= 0 n)) (post) (body (return)))\n')

try:
    result = prova.analyse('test_ptr_mmap.prova')
    print('analyse OK')
    for r in result[1]:
        fn_name = r['fn']
        lin_errs = r['linear_errors']
        obs_len = len(r['obligations'])
        print(f'  {fn_name}: linear={lin_errs}, obligations={obs_len}')
except Exception as e:
    print(f'analyse error: {e}')
"
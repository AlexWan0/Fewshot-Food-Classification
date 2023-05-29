import time
import json

def has_blacklist_keywords(title, blacklist_keywords):
    return any([keyword in title for keyword in blacklist_keywords])

def retry(func, default, num_retries=5, timeout=120):
    if num_retries <= 0:
        print(f'No more retries. Returning default={default}')
        return default

    try:
        return func()
    except Exception as e:
        print(e)
        print(f'num_retries={num_retries}, timeout={timeout}')
        time.sleep(timeout)
        return retry(func, default, num_retries=(num_retries - 1), timeout=timeout)

def count_nested_list(lst):
    return sum([count_nested_list(l) if isinstance(l, list) else 1 for l in lst])

def read_jsonl(fn):
    with open(fn) as f_in:
        return [json.loads(line) for line in f_in if len(line.strip()) > 0]

def is_valid_image(link):
    if '/commons/' not in link:
        return False
    
    if 'Flag of' in link:
        return False
    
    if 'Wiki' in link:
        return False

    if link.endswith('.svg'):
        return False

    return True

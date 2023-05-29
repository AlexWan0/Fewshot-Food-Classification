import wikipediaapi # wikipediaapi can handle categories, but not images
import wikipedia # wikipedia can handle images, but not categories :/
import argparse
import json
import time
import pickle
import tqdm

parser = argparse.ArgumentParser(description="Gets article data from wikpedia.")
parser.add_argument('--category', default="Category:Salads", type=str, help='Starting category for scrape (root node).')
parser.add_argument('--out_file', default="dataset/salads/article_text_cleanimages.json", type=str, help='Output file.')
parser.add_argument('--out_hierarchy', default="dataset/salads/article_hierarchy.pkl", type=str, help='Output for wikipedia article hierarchy.')
parser.add_argument('--max_depth', default=3, type=int, help='Maximum depth of nested categories to find articles.')
parser.add_argument('--timeout', default=0.05, type=float, help='Timeout at each iteration.')
parser.add_argument('--save_interval', default=100, type=int, help='Save temp article text at this interval when getting article data from hierarchy.')

parser.add_argument('--from_hierarchy', default=None, type=str, help='Get article from hierarchy pkl file.', required=False)

args = parser.parse_args()

# util function
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

# init api
wiki_wiki = wikipediaapi.Wikipedia(language='en')

# get page hierarchy from starting category
category_member_blacklist = ['by country', 'by nationality'] # skip similar meta category listings
def get_category_members(category, level=0, max_level=3, verbose=True):
    depth_result = [category]
    total = 0

    def _category_members():
        return category.categorymembers

    category_members = retry(_category_members, default={})

    for c in category_members.values():
        if verbose:
            print("%s: %s (ns: %d)" % ("*" * (level + 1), c.title, c.ns))
        
        if has_blacklist_keywords(c.title, category_member_blacklist):
            continue

        if c.ns == wikipediaapi.Namespace.CATEGORY and level < max_level:
            members, count = get_category_members(c, level=level + 1, max_level=max_level)
            depth_result.append(members)
            total += count
        else:
            depth_result.append(c)
            total += 1
        
        time.sleep(args.timeout)

    return depth_result, total

result = None
count = None
if args.from_hierarchy is None:
    cat = wiki_wiki.page(args.category)
    result, count = get_category_members(cat, max_level=args.max_depth)

    with open(args.out_hierarchy, 'wb') as f_out:
        pickle.dump(result, f_out)

    print("found %d articles" % count)
else:
    with open(args.from_hierarchy, 'rb') as f_in:
        result = pickle.load(f_in)
    
    count = count_nested_list(result)

    print("loaded %d articles from %s" % (count, args.from_hierarchy))

# flatten hierarchy and get article data from articles
def get_data_from_article(article_obj):
    result = {}

    def _add_attributes():
        result['pageid'] = article_obj.pageid
        result['title'] = article_obj.title
        result['text'] = article_obj.text
        result['summary'] = article_obj.summary

    retry(_add_attributes, default=None, num_retries=2)

    time.sleep(args.timeout)

    def _add_images():
        try:
            page = wikipedia.page(pageid=article_obj.pageid, auto_suggest=False)
            result['images'] = page.images
        except Exception as e: # do better error handling lol
            if str(e) == "'WikipediaPage' object has no attribute 'title'":
                return None
            else:
                raise e
    
    retry(_add_images, default=None, num_retries=2)

    return result

pbar = tqdm.trange(0, count)
counter = 0

dfs_blacklist = ['List of', 'Category:', 'Template:', 'Talk:']
article_data = []
def dfs(article_graph):
    global counter

    if isinstance(article_graph, list):
        for article in article_graph:
            dfs(article)
    else:
        title = article_graph.title
        if not has_blacklist_keywords(title, dfs_blacklist):
            pbar.write(article_graph.title)
            article_data.append(get_data_from_article(article_graph))

        if counter != 0 and counter % args.save_interval == 0:
            checkpoint_fp = args.out_file.strip() + '_temp'
            pbar.write('Saving to %s' % checkpoint_fp)

            with open(checkpoint_fp, 'w') as f_out:
                json.dump(article_data, f_out)

        pbar.update()
        counter += 1

# outputs to article_data list
dfs(result)

# clean image links
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

def prune_image_links(ex):
    if 'images' not in ex:
        ex['images'] = []
        return ex
    
    image_links = ex['images']
    image_links = list(filter(is_valid_image, image_links))
    ex['images'] = image_links
    return ex

article_data = list(map(prune_image_links, article_data))

# output to file
with open(args.out_file, 'w') as f_out:
    json.dump(article_data, f_out)

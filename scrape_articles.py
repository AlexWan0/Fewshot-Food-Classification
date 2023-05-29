import wikipediaapi # wikipediaapi can handle categories, but not images
import wikipedia # wikipedia can handle images, but not categories :/
import argparse
import json
import time

parser = argparse.ArgumentParser(description="Gets article data from wikpedia.")
parser.add_argument('--category', default="Category:Salads", type=str, help='Starting category for scrape (root node).')
parser.add_argument('--out_file', default="dataset/salads/article_text_cleanimages.json", type=str, help='Output file.')
parser.add_argument('--max_depth', default=3, type=int, help='Maximum depth of nested categories to find articles.')
parser.add_argument('--timeout', default=0.05, type=float, help='Timeout at each iteration.')
args = parser.parse_args()

# util function
def has_blacklist_keywords(title, blacklist_keywords):
    return any([keyword in title for keyword in blacklist_keywords])

# init api
wiki_wiki = wikipediaapi.Wikipedia(language='en')

# get page hierarchy from starting category
category_member_blacklist = ['by country']
def get_category_members(categorymembers, level=0, max_level=3, verbose=True):
    depth_result = []
    total = 0
    for c in categorymembers.values():
        if verbose:
            print("%s: %s (ns: %d)" % ("*" * (level + 1), c.title, c.ns))
        
        if has_blacklist_keywords(c.title, category_member_blacklist):
            continue

        if c.ns == wikipediaapi.Namespace.CATEGORY and level < max_level:
            members, count = get_category_members(c.categorymembers, level=level + 1, max_level=max_level)
            depth_result.append(members)
            total += count
        else:
            depth_result.append(c)
            total += 1
        
        time.sleep(args.timeout)

    return depth_result, total

cat = wiki_wiki.page(args.category)
result, count = get_category_members(cat.categorymembers, max_level=args.max_depth)

print("found %d articles" % count)

# flatten hierarchy and get article data from articles
def get_data_from_article(article_obj):
    result = {}

    result['pageid'] = article_obj.pageid
    result['title'] = article_obj.title
    result['text'] = article_obj.text
    result['summary'] = article_obj.summary

    try:
        page = wikipedia.page(pageid=article_obj.pageid, auto_suggest=True)
        result['images'] = page.images
    except Exception as e:
        print(e)

    return result

dfs_blacklist = ['List of', 'Category:', 'Template:']
article_data = []
def dfs(article_graph):
    if isinstance(article_graph, list):
        for article in article_graph:
            dfs(article)
    else:
        title = article_graph.title
        if not has_blacklist_keywords(title, dfs_blacklist):
            print(article_graph.title)
            article_data.append(get_data_from_article(article_graph))

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

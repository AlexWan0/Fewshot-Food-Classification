from itertools import chain
import argparse
import json
import requests
import os
from PIL import Image, UnidentifiedImageError
from glob import glob
from datasets import Dataset, DatasetDict
import random

parser = argparse.ArgumentParser(description="Downloads images and outputs to huggingface dataset.")
parser.add_argument('--article_file', default="dataset/salads/article_text_cleanimages.json", type=str, help='[INPUT] Input file.')
parser.add_argument('--user_agent_file', default="USER_AGENT.txt", type=str, help='[INPUT] File containing useragent to use when downloading wikimedia images.')

parser.add_argument('--dataset_dir', default="dataset/salads/salad_dataset/", type=str, help='[OUTPUT] Directory to save dataset.')
parser.add_argument('--url_mapping', default="dataset/salads/url_to_id.json", type=str, help='[OUTPUT] Mapping file from urls to filename ids.')
parser.add_argument('--label_mapping', default="dataset/salads/mapping.json", type=str, help='[OUTPUT] Mapping file from label name to index.')
parser.add_argument('--image_dir', default="dataset/salads/salad_images", type=str, help='[OUTPUT] Directory to save downloaded images.')

parser.add_argument('--test_size', default=0.1, type=float, help='[CONFIG] Size of test split.')

args = parser.parse_args()

with open(args.article_file) as f_in:
    article_data = json.load(f_in)

just_urls = list(chain(*[ex['images'] for ex in article_data]))
ids = list(range(len(just_urls)))

url_to_id = {url: idx for url, idx in zip(just_urls, ids)}

# download images
headers = {
    'User-Agent': open('USER_AGENT.txt').read(),
    'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
}

base_dir = args.image_dir

for url, idx in zip(just_urls, ids):
    extension = url.split('.')[-1]
    out_fp = os.path.join(base_dir, f'{idx}.{extension}')
    print(f'{url} -> {out_fp}')

    img_data = requests.get(url, headers=headers).content

    try:
        if '<!DOCTYPE html>' in img_data.decode():
            raise Exception(f'Not an image: {img_data}')
    except (UnicodeDecodeError, AttributeError):
        pass

    with open(out_fp, 'wb') as img_out:
        img_out.write(img_data)

# make huggingface dataset from images
# tries to match the format of food101
def dataset_generator():
    for ex in article_data:
        for url in ex['images']:
            url_idx = url_to_id[url]

            found_fp = glob(f'{args.image_dir}/{url_idx}.*')
            assert len(found_fp) == 1

            img_fp = found_fp[0]
            
            try:
                image = Image.open(img_fp)
            except UnidentifiedImageError:
                continue

            ex_copy = dict(ex)
            del ex_copy['images']

            ex_copy['image'] = image
            yield ex_copy

img_dataset = Dataset.from_generator(dataset_generator)

# convert text labels to integer labels
# the title of the article is the label fo the image
label_to_idx = {label: idx for idx, label in enumerate(set(img_dataset['title']))}

def add_label(ex):
    label_idx = label_to_idx[ex['title']]
    ex['label'] = label_idx

    return ex

img_dataset = img_dataset.map(add_label)

#img_dataset = img_dataset.train_test_split(test_size=0.1, train_size=0.9, shuffle=True)

# label to dataset indices mapping
label_index = {}
for i, lbl in enumerate(img_dataset['label']):
    if lbl not in label_index:
        label_index[lbl] = []
    
    label_index[lbl].append(i)

# train test split, stratified over labels
train_indices = []
test_indices = []

for lbl_indices in label_index.values():
    if len(lbl_indices) <= 1:
        continue
    
    num_samples = int(args.test_size * len(lbl_indices))

    if num_samples == 0:
        num_samples = 1
    
    sample_indices = set(random.sample(range(len(lbl_indices)), num_samples))
    test_indices.extend([lbl_indices[s_idx] for s_idx in sample_indices])
    train_indices.extend([l_idx for l_idx in lbl_indices if l_idx not in sample_indices])

img_dataset = DatasetDict({
    'train': img_dataset.select(train_indices),
    'validation': img_dataset.select(test_indices),
})

# write files
with open(args.url_mapping, 'w') as f_out:
    json.dump(url_to_id, f_out)

with open(args.label_mapping, 'w') as f_out:
    json.dump(label_to_idx, f_out)

img_dataset.save_to_disk(args.dataset_dir)

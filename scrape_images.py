from itertools import chain
import argparse
import json
import requests
import os
from PIL import Image, UnidentifiedImageError
from glob import glob
from datasets import Dataset, DatasetDict
import random
import tqdm
from scrape_utils import retry
import time
from functools import partial
from PIL import Image, ImageOps                                                       
Image.MAX_IMAGE_PIXELS = 1000_000_000

parser = argparse.ArgumentParser(description="Downloads images and outputs to huggingface dataset.")
parser.add_argument('--article_file', default="dataset/salads/article_text_cleanimages.json", type=str, help='[INPUT] Input file.')
parser.add_argument('--user_agent_file', default="USER_AGENT.txt", type=str, help='[INPUT] File containing useragent to use when downloading wikimedia images.')

parser.add_argument('--dataset_dir', default="dataset/salads/salad_dataset/", type=str, help='[OUTPUT] Directory to save dataset.')
parser.add_argument('--url_mapping', default="dataset/salads/url_to_id.json", type=str, help='[OUTPUT] Mapping file from urls to filename ids.')
parser.add_argument('--label_mapping', default="dataset/salads/mapping.json", type=str, help='[OUTPUT] Mapping file from label name to index.')
parser.add_argument('--image_dir', default="dataset/salads/salad_images", type=str, help='[OUTPUT] Directory to save downloaded images.')

parser.add_argument('--test_size', default=0.1, type=float, help='[CONFIG] Size of test split.')
parser.add_argument('--timeout', default=0.1, type=float, help='[CONFIG] Timeout at each iteration for image download.')
parser.add_argument('--skip_downloaded', default=True, type=bool, help='[CONFIG] Skip already downloaded files.')
parser.add_argument('--num_workers', default=4, type=int, help='[CONFIG] Number of processes for generating huggingface dataset.')
parser.add_argument('--image_size', default=512, type=int, help='[CONFIG] Maximum width and height of image.')

args = parser.parse_args()

article_data_file = open(args.article_file)

just_urls = list(chain(*[json.loads(line)['images'] for line in article_data_file if len(line) > 0]))
ids = list(range(len(just_urls)))

print('found %d urls' % len(just_urls))

article_data_file.seek(0)

url_to_id = {url: idx for url, idx in zip(just_urls, ids)}

with open(args.url_mapping, 'w') as f_out:
    json.dump(url_to_id, f_out)

# download images
with open(args.user_agent_file) as f_in:
    user_agent_string = f_in.read().strip()

headers = {
    'User-Agent': user_agent_string,
    'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
}

def _download_image(url, out_fp):
    img_data = requests.get(url, headers=headers).content

    try:
        if '<!DOCTYPE html>' in img_data.decode():
            raise Exception(f'Not an image: {img_data}')
    except (UnicodeDecodeError, AttributeError):
        pass

    with open(out_fp, 'wb') as img_out:
        img_out.write(img_data)

base_dir = args.image_dir

# pbar_download = tqdm.tqdm(zip(just_urls, ids), total=len(ids))
# for url, idx in pbar_download:
#     extension = url.split('.')[-1]
#     out_fp = os.path.join(base_dir, f'{idx}.{extension}')
#     pbar_download.write(f'{url} -> {out_fp}')

#     if args.skip_downloaded and len(glob(f'{args.image_dir}/{idx}.*')) >= 1:
#         pbar_download.write(f'id={idx} has already been downloaded, skipping.')
#         continue
    
#     retry(partial(_download_image, url, out_fp), None, num_retries=2)

#     time.sleep(args.timeout)

# make huggingface dataset from images
# tries to match the format of food101

def preprocess_image(pil_image):
    return ImageOps.contain(pil_image, (args.image_size, args.image_size))

# count num files to process (for multiprocessing)
num_lines = sum(1 for _ in article_data_file)
article_data_file.close()

samples_per_worker = num_lines // args.num_workers

def get_images(ex, pbar):
    for url in ex['images']:
        url_idx = url_to_id[url]

        found_fp = glob(f'{args.image_dir}/{url_idx}.*')

        if len(found_fp) == 0:
            pbar.write(f'No image for id={url_idx} found.')
            continue

        assert len(found_fp) == 1

        img_fp = found_fp[0]
        
        try:
            image = Image.open(img_fp)
        except UnidentifiedImageError:
            pbar.write(f'Error opening image for id={url_idx}')
            continue

        ex_copy = dict(ex)
        del ex_copy['images']

        ex_copy['image'] = preprocess_image(image)
        
        yield ex_copy

def dataset_generator(rank):
    rank = rank[0]

    from_idx = rank * samples_per_worker

    if rank != (args.num_workers - 1):
        to_idx = (rank + 1) * samples_per_worker
    else:
        to_idx = num_lines

    pbar_dataset = tqdm.trange(0, to_idx - from_idx, position=(rank + 1))
    pbar_dataset.set_description(f'rank={rank}')

    with open(args.article_file) as worker_article_file:
        for i, line in enumerate(worker_article_file):
            if len(line) == 0:
                continue
            
            # maybe cache linebreak positions so you don't have to needlessly iterate?
            if i < from_idx:
                continue

            if i >= to_idx:
                break

            ex = json.loads(line)

            yield from get_images(ex, pbar_dataset)
            
            pbar_dataset.update()

img_dataset = Dataset.from_generator(
    dataset_generator,
    num_proc=args.num_workers,
    gen_kwargs={'rank': list(range(args.num_workers))}
)

# convert text labels to integer labels
# the title of the article is the label fo the image
label_to_idx = {label: idx for idx, label in enumerate(set(img_dataset['title']))}

with open(args.label_mapping, 'w') as f_out:
    json.dump(label_to_idx, f_out)

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
        train_indices.extend(lbl_indices)
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

print('items in train:', len(img_dataset['train']))
print('items in validation:', len(img_dataset['validation']))

# write files
img_dataset.save_to_disk(args.dataset_dir)

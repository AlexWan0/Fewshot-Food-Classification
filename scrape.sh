#!/bin/bash

name='test'

mkdir dataset/$name
mkdir dataset/$name/images

python scrape_articles.py \
    --category "Category:Noodles" \
    --out_file dataset/$name/article_text.json \
    --max_depth 0

python scrape_images.py \
    --article_file dataset/$name/article_text.json \
    --dataset_dir dataset/$name/dataset \
    --url_mapping dataset/$name/url_mapping.json \
    --label_mapping dataset/$name/label_mapping.json \
    --image_dir dataset/$name/images


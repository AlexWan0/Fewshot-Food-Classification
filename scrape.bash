python scrape_articles.py \
    --category "Category:Noodles" \
    --out_file dataset/test/article_text.json \
    --max_depth 0

python scrape_images.py \
    --article_file dataset/test/article_text.json \
    --dataset_dir dataset/test/dataset \
    --url_mapping dataset/test/url_mapping.json \
    --label_mapping dataset/test/label_mapping.json \
    --image_dir dataset/test/images

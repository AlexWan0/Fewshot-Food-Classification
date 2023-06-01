## Few-shot open-domain food classification from Wikipedia articles

The goal is to classify *arbitrary* images of food based on images & descriptions scraped from Wikipedia articles. Would be cool to take advantage of category hierarchies as well.

Currently have a rough implementation of [TIP-Adapter](https://github.com/gaopengcuhk/Tip-Adapter) and dataset gathering from Wikipedia. Parsing Wikipedia archives is probably a better idea than scraping, though.

Dataset containing images and articles from the "Cuisine by Country" category can be found [here](https://huggingface.co/datasets/alexwan0/wikipedia-foods). The labels are labels corresponding to the page titles. The mapping can also be found in `dataset/cuisine_by_country/label_mapping.json` Removal of some labels may be needed (e.g., the `National Food` page).

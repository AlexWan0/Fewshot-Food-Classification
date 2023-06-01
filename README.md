## Few-shot open-domain food classification from Wikipedia articles
The goal is to classify *arbitrary* images of food based on images & descriptions scraped from Wikipedia articles. There are 17,570 classes total.

## Model
The model is an implementation of [TIP-Adapter](https://github.com/gaopengcuhk/Tip-Adapter). 

I use the `openai/clip-vit-large-patch14` for the image and text embeddings. 

I made two changes:

* Some labels have different numbers of few-shot examples. In the matrix multiply, I scale by the number of examples available (i.e., I average over the image similarity logits).
* ~~Instead of using text templates to generate the text-embeddings from the class labels, I use the first sentence of their Wikipedia article. I compare the performance of this below.~~ jk this doesn't actually work better (yet)

I also run a small hyperparameter sweep over the `alpha` and `beta` parameters.

## Dataset
The dataset containing images and articles from the "Cuisine by Country" category can be found [here](https://huggingface.co/datasets/alexwan0/wikipedia-foods). The labels are indices corresponding to the page titles. The mapping can also be found in `dataset/cuisine_by_country/label_mapping.json`. Removal of some labels may be needed (e.g., the `National Food` page).

There are `59048` images in the training set and `11684` in the validation set. For classes with at least 2 images, at least one will be used during testing. Classes with only 1 image aren't tested.

## Performance
### With basic text template 
Template: `'A photo of a {name}. A picture of food.'`

Hyperparameters: `{'alpha': 1, 'beta': 5}`

Top-1 accuracy: `0.5237932214994865`

Top-5 accuracy: `0.6553406367682301`

### With Wikipedia article
Use first sentence of article. Truncate if text is longer than max length supported by model.

Hyperparameters: `{'alpha': 2, 'beta': 5}`

Top-1 accuracy: `0.5258473125641904`

Top-5 accuracy: `0.65619650804519`

## Todo
* Finetune an MLP on the CLIP embeddings
* Train a model on article text (or find some heuristic) to remove non-food articles
* Test other CLIP models
* Take advantage of article hierarchy
* Better text embeddings -- I feel like there's a lot more you could do with Wikipedia descriptions of classes than just taking the first `k` sentences.

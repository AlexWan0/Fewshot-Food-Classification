import json
from transformers import CLIPProcessor, CLIPModel
import torch
import pickle
from torch.nn import functional as F
from PIL import Image
import requests
from io import BytesIO
from scrape_utils import has_blacklist_keywords
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--model_name", default="openai/clip-vit-large-patch14")
parser.add_argument("--label_mapping", default="dataset/cuisine_by_country/label_mapping.json")
parser.add_argument("--text_embeds", default="ref_text_article.pt")
parser.add_argument("--image_embeds", default="ref_images.pt")
parser.add_argument("--training_labels", default="labels_all.pkl")

parser.add_argument("--user_agent", default='USER_AGENT.txt')

parser.add_argument("--top_k", default=20)

parser.add_argument("--alpha", default=2.0)
parser.add_argument("--beta", default=5.0)

args = parser.parse_args()

def load_clip_model(device='cuda', model_name=args.model_name):
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    model.to(device)

    processor = CLIPProcessor.from_pretrained(model_name)

    return model, processor

def infer_single(test_image, beta=1.0, alpha=1.0):
    test_image_embeds = model(
        **(processor(images=test_image, text='', return_tensors="pt", padding=True).to('cuda'))
    ).image_embeds.cpu()

    img_sim = torch.matmul(test_image_embeds, ref_images.T)
    img_sim = ((-1) * (beta - beta * img_sim)).exp()
    class_sim_img = torch.matmul(img_sim, labels_oh) # (1, num_classes)

    class_sim_text = torch.matmul(test_image_embeds, ref_text.T) # (1, num_classes)

    class_sim = alpha * class_sim_img + class_sim_text # (1, num_classes)

    return class_sim

print("Loading labels...")
with open(args.label_mapping) as f_in:
    name_to_index = json.load(f_in)

index_to_name = {v: k for k, v in name_to_index.items()}
num_classes = len(index_to_name)

print("Loading model...")
model, processor = load_clip_model()

print("Loading embeds...")
with open(args.text_embeds, 'rb') as f_in:
    ref_text = torch.load(f_in)

with open(args.image_embeds, 'rb') as f_in:
    ref_images = torch.load(f_in)

with open(args.training_labels, 'rb') as f_in:
    labels_all = pickle.load(f_in)

labels_oh = F.one_hot(torch.tensor(labels_all), num_classes=num_classes).float()
labels_oh = labels_oh / torch.sum(labels_oh, dim=0, keepdim=True)
assert not torch.isnan(labels_oh).any()

# for downloading images
with open(args.user_agent) as f_in:
    user_agent_string = f_in.read().strip()

headers = {
    'User-Agent': user_agent_string,
    'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
}

blacklist_keywords = ['cuisine']

while True:
    input_fp = input("Enter file path or link to image: ")

    if input_fp == '':
        exit()

    try:
        if 'http' in input_fp:
            print('Link detected, downloading image...')

            response = requests.get(input_fp, headers={})
            image = Image.open(BytesIO(response.content))
        else:
            image = Image.open(input_fp)
    except Exception as e:
        print(e)
        print("Error opening file.")
        continue

    logits = infer_single(image, alpha=args.alpha, beta=args.beta)
    preds_top_k = torch.sort(logits, descending=True)[1][0,:]
    
    preds_top_k_name = [index_to_name[p_idx.item()] for p_idx in preds_top_k]
    
    preds_top_k_name = filter(
        lambda label_name: not has_blacklist_keywords(
            label_name,
            blacklist_keywords=blacklist_keywords,
            lower=True
        ),
        preds_top_k_name
    )

    preds_top_k_name = list(preds_top_k_name)

    print('PREDICTIONS:')
    print('\n'.join(preds_top_k_name[:args.top_k]))
    print('-' * 50)

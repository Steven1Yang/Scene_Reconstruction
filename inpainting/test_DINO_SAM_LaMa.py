import torch
from PIL import Image
import numpy as np
import argparse
import os
import shutil
from pathlib import Path
from tqdm import tqdm
import groundingdino.datasets.transforms as T
from groundingdino.models import build_model
from groundingdino.util.slconfig import SLConfig
from groundingdino.util.utils import clean_state_dict, get_phrases_from_posmap
from sammm.segment_anything import sam_model_registry, SamPredictor
import cv2

from lama_inpaint import inpaint_img_with_lama

device = "cuda" if torch.cuda.is_available() else "cpu"

def load_model(model_config_path, model_checkpoint_path, bert_base_uncased_path, device):
    args = SLConfig.fromfile(model_config_path)
    args.device = device
    args.bert_base_uncased_path = bert_base_uncased_path
    model = build_model(args)
    checkpoint = torch.load(model_checkpoint_path, map_location="cpu")
    model.load_state_dict(clean_state_dict(checkpoint["model"]), strict=False)
    model.eval()
    return model

def get_grounding_output(model, image, caption, box_threshold, text_threshold, device="cpu"):
    caption = caption.lower().strip()
    if not caption.endswith("."):
        caption = caption + "."
    model = model.to(device)
    image = image.to(device)
    with torch.no_grad():
        outputs = model(image[None], captions=[caption])
    logits = outputs["pred_logits"].cpu().sigmoid()[0]  # (nq, 256)
    boxes = outputs["pred_boxes"].cpu()[0]  # (nq, 4)
    filt_mask = logits.max(dim=1)[0] > box_threshold
    logits_filt = logits[filt_mask]
    boxes_filt = boxes[filt_mask]
    tokenlizer = model.tokenizer
    tokenized = tokenlizer(caption)
    pred_phrases = []
    for logit, box in zip(logits_filt, boxes_filt):
        pred_phrase = get_phrases_from_posmap(logit > text_threshold, tokenized, tokenlizer)
        pred_phrases.append(pred_phrase + f"({str(logit.max().item())[:4]})")
    return boxes_filt, pred_phrases

def transform_image(image_pil):
    transform = T.Compose([
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    image, _ = transform(image_pil, None)
    return image

def dino_boxes_to_pixel_xyxy(boxes, image_size):
    W, H = image_size
    boxes_pixel = boxes.clone()
    boxes_pixel[:, 0] = boxes[:, 0] * W
    boxes_pixel[:, 1] = boxes[:, 1] * H
    boxes_pixel[:, 2] = boxes[:, 2] * W
    boxes_pixel[:, 3] = boxes[:, 3] * H
    boxes_xyxy = torch.zeros_like(boxes_pixel)
    boxes_xyxy[:, 0] = boxes_pixel[:, 0] - boxes_pixel[:, 2] / 2
    boxes_xyxy[:, 1] = boxes_pixel[:, 1] - boxes_pixel[:, 3] / 2
    boxes_xyxy[:, 2] = boxes_pixel[:, 0] + boxes_pixel[:, 2] / 2
    boxes_xyxy[:, 3] = boxes_pixel[:, 1] + boxes_pixel[:, 3] / 2
    return boxes_xyxy

def merge_masks(masks):
    if len(masks) == 0:
        return None
    merged = np.zeros_like(masks[0], dtype=np.uint8)
    for m in masks:
        merged = np.logical_or(merged, m > 0)
    return merged.astype(np.uint8) * 255

def dilate_mask(mask, kernel_size=7):
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.dilate(mask, kernel, iterations=1)

def process_one_prompt(image_np, model, sam, prompt, args):
    image_pil = Image.fromarray(image_np)
    image_tensor = transform_image(image_pil)
    boxes, phrases = get_grounding_output(
        model, image_tensor, prompt, args.box_threshold, args.text_threshold, device=device
    )
    if len(boxes) > 0:
        predictor = SamPredictor(sam)
        predictor.set_image(image_np)
        boxes_xyxy = dino_boxes_to_pixel_xyxy(boxes, image_pil.size)
        boxes_xyxy = boxes_xyxy.to(predictor.device)
        transformed_boxes = predictor.transform.apply_boxes_torch(boxes_xyxy, image_np.shape[:2])
        masks, _, _ = predictor.predict_torch(
            point_coords=None,
            point_labels=None,
            boxes=transformed_boxes,
            multimask_output=False,
        )
        masks = masks.cpu().numpy()
        masks = np.squeeze(masks, axis=1)
        merged_mask = merge_masks(masks)
        if merged_mask is not None:
            merged_mask = dilate_mask(merged_mask, kernel_size=args.dilate_kernel_size)
        return merged_mask
    else:
        return None

def main():
    parser = argparse.ArgumentParser("Batch GroundingDINO+SAM+LaMa inpainting (multi-prompt)")
    parser.add_argument("--input_dir", type=str, required=True, help="Input root directory (包含N个街景子文件夹)")
    parser.add_argument("--output_dir", type=str, required=True, help="Output root directory")
    parser.add_argument("--config", type=str, required=True, help="DINO config .py file")
    parser.add_argument("--checkpoint", type=str, required=True, help="DINO model checkpoint .pth")
    parser.add_argument("--bert_base_uncased_path", type=str, required=False, help="BERT base uncased path")
    parser.add_argument("--box_threshold", type=float, default=0.3, help="box threshold")
    parser.add_argument("--text_threshold", type=float, default=0.25, help="text threshold")
    parser.add_argument("--sam_model_type", type=str, default="vit_h", help="SAM model type: vit_h/vit_l/vit_b")
    parser.add_argument("--sam_ckpt", type=str, required=True, help="SAM checkpoint path")
    parser.add_argument("--lama_config", type=str, required=True, help="LaMa config yaml")
    parser.add_argument("--lama_ckpt", type=str, required=True, help="LaMa checkpoint path")
    parser.add_argument("--dilate_kernel_size", type=int, default=15, help="Mask dilation kernel size (default=15)")
    args = parser.parse_args()

    prompts = ["people", "car and its shadow", "car", "tree"]

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load models only once
    model = load_model(args.config, args.checkpoint, args.bert_base_uncased_path, device)
    sam = sam_model_registry[args.sam_model_type](checkpoint=args.sam_ckpt)

    print(f"Start batch inpainting (multi-prompt): {input_dir} -> {output_dir}")
    subfolders = [d for d in input_dir.iterdir() if d.is_dir()]
    for subfolder in tqdm(subfolders, desc="Folders"):
        out_subfolder = output_dir / subfolder.name
        out_subfolder.mkdir(parents=True, exist_ok=True)
        for file_path in tqdm(list(subfolder.iterdir()), desc=f"{subfolder.name}", leave=False):
            if not file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
                shutil.copy2(file_path, out_subfolder / file_path.name)
                continue
            out_img_file = out_subfolder / file_path.name
            out_mask_file = out_subfolder / f"with_mask_{file_path.stem}.png"
            out_inpaint_file = out_subfolder / f"inpainted_{file_path.name}"
            if out_inpaint_file.exists():
                continue
            image_np = cv2.imread(str(file_path))
            image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            inpainted_img = image_np.copy()
            all_masks = []
            for prompt in prompts:
                merged_mask = process_one_prompt(inpainted_img, model, sam, prompt, args)
                if merged_mask is not None and np.sum(merged_mask) > 0:
                    all_masks.append(merged_mask)
                    # save the mask for each prompt if you want
                    # cv2.imwrite(str(out_subfolder / f"mask_{prompt.replace(' ','_')}_{file_path.stem}.png"), merged_mask)
                    # inpaint
                    inpainted_img = inpaint_img_with_lama(inpainted_img, merged_mask, args.lama_config, args.lama_ckpt, device=device)
            # 保存最终合成mask（全部目标的联合mask）
            if all_masks:
                final_mask = np.zeros_like(all_masks[0])
                for m in all_masks:
                    final_mask = np.logical_or(final_mask, m>0)
                final_mask = (final_mask.astype(np.uint8)) * 255
                cv2.imwrite(str(out_mask_file), final_mask)
            # 保存最终inpaint结果
            out_img = Image.fromarray(inpainted_img)
            out_img.save(out_inpaint_file)
    print("Batch inpainting (multi-prompt) done.")

if __name__ == "__main__":
    main()
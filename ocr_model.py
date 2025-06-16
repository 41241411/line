import torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
import io

device = torch.device("cpu")
MODEL_ID = "reducto/RolmOCR"
processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=True)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32
).to(device).eval()

def ocr_image_from_bytes(image_bytes, query="請辨識圖片中的內容", max_new_tokens=512):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": query}]}]
    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[prompt], images=[image], return_tensors="pt", padding=True).to(device)
    
    outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
    result = processor.batch_decode(outputs, skip_special_tokens=True)
    text = result[0].replace("<|im_end|>", "").strip()
    lines = text.splitlines()
    return lines[-1] if lines else ""

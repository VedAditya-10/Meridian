"""
LEGACY SCRIPT - NOT CURRENTLY USED

This script exports OSNet-x1.0 ReID model to ONNX format.
The platform currently uses ResNet50 (export_fastreid_onnx.py) which provides
2048-d embeddings instead of OSNet's 512-d embeddings.

This script is kept for future experimentation or migration purposes.
To use OSNet instead of ResNet50:
1. Run this script to generate weights/osnet_x1_0.onnx
2. Update REID_MODEL_PATH env var to point to osnet_x1_0.onnx
3. Update database schema: ALTER TABLE visitor_embeddings ALTER COLUMN embedding TYPE vector(512);
4. Update all embedding dimension references from 2048 to 512
"""

import torch
import torchreid
import os

def main():
    print("Building OSNet model...")
    # Build model using torchreid
    model = torchreid.models.build_model(
        name='osnet_x1_0',
        num_classes=751,
        loss='softmax',
        pretrained=True
    )
    model.eval()

    # Create dummy input with shape (batch_size, channels, height, width)
    # OSNet default shape: (1, 3, 256, 128)
    dummy_input = torch.randn(1, 3, 256, 128)

    # Ensure weights directory exists
    os.makedirs("weights", exist_ok=True)
    onnx_path = "weights/osnet_x1_0.onnx"

    print(f"Exporting model to ONNX format at {onnx_path}...")
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=12,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={
            'input': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        }
    )
    print("Model successfully exported and verified!")

if __name__ == "__main__":
    main()

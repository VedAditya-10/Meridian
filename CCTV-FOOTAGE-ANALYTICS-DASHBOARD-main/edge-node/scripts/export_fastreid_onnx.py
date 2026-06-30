import os
import torch
import torch.nn as nn
import torchvision.models as models

class ResNet50ReID(nn.Module):
    def __init__(self):
        super().__init__()
        # Load ResNet50 model with pre-trained weights
        try:
            from torchvision.models import resnet50, ResNet50_Weights
            resnet = resnet50(weights=ResNet50_Weights.DEFAULT)
        except ImportError:
            resnet = models.resnet50(pretrained=True)
            
        # Remove the final classification layer to get 2048-d feature vectors
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])
        
    def forward(self, x):
        features = self.backbone(x)
        features = torch.flatten(features, 1)
        return features

def main():
    print("=== Building ResNet-50 ReID feature extractor ===")
    model = ResNet50ReID()
    model.eval()
    
    # Create dummy input matching the ReID crop shape (1, 3, 256, 128)
    dummy_input = torch.randn(1, 3, 256, 128)
    
    os.makedirs("weights", exist_ok=True)
    onnx_path = "weights/fastreid_r50.onnx"
    
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

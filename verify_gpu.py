"""فحص سريع للتأكد أن PyTorch يرى الـ GPU (CUDA) بشكل صحيح."""
import torch

print("torch version :", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA version  :", torch.version.cuda)
    print("GPU device    :", torch.cuda.get_device_name(0))
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU memory    : {total:.1f} GB")
else:
    print("تحذير: PyTorch لا يرى الـ GPU — سيعمل الموديل على الـ CPU (أبطأ).")

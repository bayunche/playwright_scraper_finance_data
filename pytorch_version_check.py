import torch

def check_pytorch_version():
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 是否可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"当前设备名称: {torch.cuda.get_device_name(torch.cuda.current_device())}")

if __name__ == "__main__":
    check_pytorch_version()
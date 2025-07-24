import torch

def test_cuda():
    print("检测 CUDA 是否可用...")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA 可用: {cuda_available}")
    if cuda_available:
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        print(f"CUDA 设备数量: {device_count}")
        print(f"当前设备索引: {current_device}")
        print(f"当前设备名称: {device_name}")
    else:
        print("未检测到可用的 CUDA 设备。")

if __name__ == "__main__":
    test_cuda()
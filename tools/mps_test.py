import torch
import Metal

'''
uv pip install pyobjc-framework-Metal
'''
def mps_test():

    if torch.backends.mps.is_available():
        print("MPS is available!")
        device = torch.device("mps")
        x = torch.ones(1, device=device)
        print(x)
    else:
        print("MPS device not found.")


    device = Metal.MTLCreateSystemDefaultDevice()
    vram_bytes = device.maxTransferRate()  # This may vary by Metal version

    print(f"Device name: {device.name()}")
    print(f"Recommended max working set size: {device.recommendedMaxWorkingSetSize() / (1024 ** 2):.2f} MB")
    print(f"Estimated VRAM: {vram_bytes / (1024 ** 2):.2f} MB")

if __name__ == "__main__":
    mps_test()
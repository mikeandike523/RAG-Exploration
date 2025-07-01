import torch
import pynvml

# Initialize NVML
pynvml.nvmlInit()

# How many CUDA devices are visible?
num_gpus = torch.cuda.device_count()
print(f"Number of GPUs: {num_gpus}")

# Mapping of common subsystem vendor IDs to human-readable board-partner names
vendor_map = {
    0x1462: "MSI",
    0x1458: "Gigabyte",
    0x10DE: "NVIDIA (reference)",
    0x102C: "PNY",
    0x174B: "Zotac",
    # Add more mappings as needed
}

for i in range(num_gpus):
    # PyTorch properties
    props = torch.cuda.get_device_properties(i)

    # NVML handle and PCI info
    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
    pci    = pynvml.nvmlDeviceGetPciInfo(handle)
    ss_vid = pci.pciDeviceId >> 16              # Subsystem Vendor ID
    ss_did = pci.pciDeviceId & 0xFFFF           # Subsystem Device ID
    board_vendor = vendor_map.get(ss_vid, f"Unknown (0x{ss_vid:04x})")

    # Print combined information
    print(f"\nGPU {i}:")
    print(f"  Name:               {props.name}")
    print(f"  Compute capability: {props.major}.{props.minor}")
    print(f"  Total memory:       {props.total_memory / (1024**3):.1f} GB")
    print(f"  Multiprocessors:    {props.multi_processor_count}")
    print(f"  Max threads/MP:     {props.max_threads_per_multi_processor}")
    print(f"  PCI Bus ID:         {pci.domain:04x}:{pci.bus:02x}:{pci.device:02x}")
    print(f"  Subsys Vendor ID:   0x{ss_vid:04x} ({board_vendor})")
    print(f"  Subsys Device ID:   0x{ss_did:04x}")

# Shutdown NVML
pynvml.nvmlShutdown()

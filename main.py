import torch
import time

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Используется: {device}")

# Создаём большие матрицы
size = 5000
a = torch.randn(size, size).to(device)
b = torch.randn(size, size).to(device)

# Замеряем время перемножения на GPU
start = time.time()
c = torch.mm(a, b)
torch.cuda.synchronize()  # Ждём завершения GPU операций
gpu_time = time.time() - start

print(f"GPU время: {gpu_time:.4f} секунд")

# Для сравнения — на CPU
a_cpu = a.cpu()
b_cpu = b.cpu()
start = time.time()
c_cpu = torch.mm(a_cpu, b_cpu)
cpu_time = time.time() - start

print(f"CPU время: {cpu_time:.4f} секунд")
print(f"Ускорение GPU: {cpu_time / gpu_time:.1f}x")
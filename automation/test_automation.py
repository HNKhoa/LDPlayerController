import asyncio
from automation_runner import AutomationRunner

# Đọc device_id từ file mà manual.py đã lưu
with open("adb_device.txt") as f:
    device_id = f.read().strip()

runner = AutomationRunner(device_id)

async def main():
    # 1. Tìm vị trí ảnh "test img 3.png"
    pos = runner.find_image_on_screen("img/test img 3.png")
    if pos:
        print("Tìm thấy ảnh tại:", pos)
        # 2. Click tại vị trí đó
        runner.adb_tap(*pos)
    else:
        print("Không tìm thấy ảnh.")

    # 3. Click thêm vào tọa độ (125, 90)
    runner.adb_tap(125, 90)

asyncio.run(main())

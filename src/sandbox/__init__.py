import sys


def create_sandbox():
    """按平台返回沙箱后端：macOS 用 Seatbelt，其余用 bubblewrap。"""
    if sys.platform == "darwin":
        from src.sandbox.seatbelt import SeatbeltSandbox

        return SeatbeltSandbox()

    from src.sandbox.bubblewrap import BubblewrapSandbox

    return BubblewrapSandbox()

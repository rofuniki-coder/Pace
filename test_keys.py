
import ctypes
import time
import sys

def test_keys():
    # Windows Virtual Key Codes
    VK_CONTROL = 0x11
    VK_MENU = 0x12 # ALT key
    
    def is_pressed(vk):
        # Direct Windows API call for physical key state
        # 0x8000 is the bitmask for "currently held down"
        return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0

    print("Testing GetAsyncKeyState for CTRL + ALT...")
    print("Press CTRL+ALT now (or ESC to exit).")
    
    try:
        while True:
            ctrl = is_pressed(VK_CONTROL)
            alt = is_pressed(VK_MENU)
            esc = is_pressed(0x1B) # VK_ESCAPE
            
            if ctrl and alt:
                print("\r[TRIGGERED] CTRL + ALT detected!          ", end="")
            elif ctrl:
                print("\r[PARTIAL] CTRL detected...                ", end="")
            elif alt:
                print("\r[PARTIAL] ALT detected...                 ", end="")
            else:
                print("\r[WAITING] No keys detected...             ", end="")
            
            if esc:
                print("\nExiting test.")
                break
                
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nTest interrupted.")

if __name__ == "__main__":
    test_keys()

"""Run the standalone Phase 1 UI. No real application modules are imported."""
import tkinter as tk
from studio_ui.app import StudioPreview


def main():
    root=tk.Tk()
    StudioPreview(root)
    root.mainloop()


if __name__=='__main__':main()

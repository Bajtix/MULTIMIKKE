import tkinter.simpledialog
import tkinter as tk
from tkinter import BOTTOM, ttk
import tkinter.simpledialog


class ComboDialog(tkinter.simpledialog.Dialog):
    def __init__(self, parent, title=None, list=[]):
        self.list = list
        super().__init__(parent, title=title)

    def body(self, master):
        self.box = ttk.Combobox(
            master, values=self.list, width=50, state="readonly")
        self.box.pack()
        self.box.current(0)
        self.val = None
        return self.box  # initial focus

    def apply(self):
        self.val = self.list.index(self.box.get())
        return self.val

    def getresult(self):
        return self.val


def askcombo(title=None, list=[]):
    d = ComboDialog(None, title=title, list=list)
    return d.result

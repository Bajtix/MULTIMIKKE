from email.mime import audio
import subprocess
import tkinter as tk
import threading
from tkinter import BOTTOM, CENTER, LEFT, RIGHT, TOP, StringVar, ttk
from tkinter import messagebox
import audioop
from tkinter import simpledialog
import wave
import os
import json
from pydub import AudioSegment
from PIL import Image, ImageTk
import shutil
from pympler import asizeof
import time
import datetime

import customcompo
import audiohost
import util


serverThread = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        audiohost.Init()

        # configure the root window
        self.title('MULTIMIKKE')
        self.geometry('800x500')
        self.minsize = (800, 500)

        # COLORS
        self.defaultBg = "#009faa"
        self.defaultFg = "#ffffff"
        self.darkBg = "#007faa"
        self.genericBg = "#dddddd"
        self.activeColor = "#0e8428"
        self.focusedColor = "#2de5ab"

        # VARIABLES

        self.mikesCount = StringVar(self, "Witamy w MULTIMIKKE!")
        self.mikePanels = {}

        self.sceneVar = tk.IntVar(self, value=1)
        self.takeVar = tk.IntVar(self, value=1)
        self.partVar = tk.IntVar(self, value=1)
        self.recTime = tk.StringVar(self, value="Powodzenia z nagraniem!")

        self.recBuffer = {}
        self.isRecording = False
        self.recStartTime = datetime.datetime.now()
        self.lastCheck = datetime.datetime.now()

        self.LoadData()
        # funny trick to make it safer
        audiohost.SetOutputDevice(audiohost.outputDevice)

        # ICONS

        self.iconBgGraphic = Image.open(
            "res/background.png").resize((500, 500))
        self.iconBgRecGraphic = Image.open(
            "res/background-rec.png").resize((500, 500))
        self.iconDirGraphic = Image.open("res/icon_dir.png").resize((16, 16))
        self.iconSpeakerGraphic = Image.open(
            "res/icon_speaker.png").resize((16, 16))
        self.iconBinGraphic = Image.open("res/icon_bin.png").resize((16, 16))
        self.iconCDGraphic = Image.open("res/icon_cd.png").resize((16, 16))

        self.iconBg = ImageTk.PhotoImage(self.iconBgGraphic)
        self.iconBgRec = ImageTk.PhotoImage(self.iconBgRecGraphic)
        self.iconDir = ImageTk.PhotoImage(self.iconDirGraphic)
        self.iconSpeaker = ImageTk.PhotoImage(self.iconSpeakerGraphic)
        self.iconBin = ImageTk.PhotoImage(self.iconBinGraphic)
        self.iconCD = ImageTk.PhotoImage(self.iconCDGraphic)

        # MIKES

        self.pnlMikes = ttk.Frame(self)
        self.pnlMikes.pack(side=TOP, fill=tk.BOTH, expand=True)

        self.bgImg = ttk.Label(self.pnlMikes, image=self.iconBg)
        self.bgImg.place(anchor=tk.CENTER, relx=0.5, rely=0.5)

        # Mike CONTROL

        self.pnlServerControl = ttk.Frame(
            self)
        self.pnlServerControl.pack(side=BOTTOM, fill=tk.X)

        self.btnAdd = ttk.Button(
            self.pnlServerControl, text='Dodaj Lokalny (A)', command=self.AddLocalMike, width=20, takefocus=0)
        self.btnAdd.pack(side=RIGHT)

        self.btnStart = ttk.Button(
            self.pnlServerControl, text='Wystartuj TCP (^A)', command=self.ToggleServer, width=20, takefocus=0)
        self.btnStart.pack(side=RIGHT)

        self.lblConnected = ttk.Label(
            self.pnlServerControl, textvariable=self.mikesCount)
        self.lblConnected.pack(side=LEFT)

        # PREVIEW PANEL

        self.pnlPreview = ttk.Frame(self)
        self.pnlPreview.pack(side=BOTTOM, fill=tk.X)

        self._lbl = ttk.Label(self.pnlPreview, text="PODSŁUCH ")
        self._lbl.pack(side=LEFT)

        self.sldVolume = ttk.Scale(
            self.pnlPreview, from_=0, to=300, orient=tk.HORIZONTAL, value=audiohost.playbackVolumes["main"], command=lambda v: self.SetAmplify("main", v), length=170)
        self.sldVolume.pack(side=LEFT, fill=tk.X)

        self.btnMute = ttk.Button(
            self.pnlPreview, text="Wył. Podsłuch (M)", command=lambda: self.SetListen("muted"), width=20, takefocus=0)
        self.btnMute.pack(side=RIGHT)

        self.btnSetOutput = ttk.Button(
            self.pnlPreview, text="Wybierz wyjście (^M)", command=lambda: self.AskChangeOutput(), width=20, takefocus=0)
        self.btnSetOutput.pack(side=RIGHT)

        self.btnSyncPlayback = ttk.Button(
            self.pnlPreview, text="Sync", command=lambda: audiohost.BufferClear(), width=5)
        self.btnSyncPlayback.pack(side=RIGHT)

        # RECORDER

        self.pnlRec = ttk.Frame(self)
        self.pnlRec.pack(side=BOTTOM, fill=tk.X)

        self._lbl = ttk.Label(self.pnlRec, text="SCENA ")
        self._lbl.pack(side=LEFT)

        numberValidator = (self.register(util.validate_spinbox), '%d', '%P')

        self.whlScene = ttk.Spinbox(
            self.pnlRec, from_=1, to=999, width=3, textvariable=self.sceneVar, command=lambda: self.takeVar.set(1), validate="key", validatecommand=numberValidator)
        self.whlScene.pack(side=LEFT)

        self._lbl = ttk.Label(self.pnlRec, text=" CZĘŚĆ ")
        self._lbl.pack(side=LEFT)

        self.whlPart = ttk.Spinbox(
            self.pnlRec, from_=1, to=50, width=3, textvariable=self.partVar, validate="key", validatecommand=numberValidator)
        self.whlPart.pack(side=LEFT)

        self._lbl = ttk.Label(self.pnlRec, text=" UJĘCIE ")
        self._lbl.pack(side=LEFT)

        self.whlTake = ttk.Spinbox(
            self.pnlRec, from_=1, to=999, width=3, textvariable=self.takeVar, validate="key", validatecommand=numberValidator)
        self.whlTake.pack(side=LEFT)

        self.lblRecTime = ttk.Label(
            self.pnlRec, textvariable=self.recTime)
        self.lblRecTime.pack(side=LEFT, fill=tk.X, padx=(5, 0))

        self.btnRecord = ttk.Button(self.pnlRec, text="Nagraj (R)",
                                    command=self.Record, style="TButton", state=tk.NORMAL, width=20, takefocus=0)
        self.btnRecord.pack(side=RIGHT)

        self.btnPlayScene = ttk.Button(self.pnlRec, image=self.iconCD, text="O", compound=tk.LEFT,
                                       command=self.OpenMixedRecording, style="TButton", state=tk.NORMAL, width=6, takefocus=0)
        self.btnPlayScene.pack(side=RIGHT)

        self.btnViewScene = ttk.Button(self.pnlRec, image=self.iconDir, text="^O", compound=tk.LEFT,
                                       command=self.OpenFolder, style="TButton", state=tk.NORMAL, width=6, takefocus=0)
        self.btnViewScene.pack(side=RIGHT)

        # STYLE

        self.style = ttk.Style(self)
        self.style.theme_use("alt")

        self.style.configure("TFrame", padding=(
            10, 10, 10, 10), relief=tk.GROOVE, borderwidth=1, font=("Arial", 12), background="#009faa")

        self.style.configure("Dark.TFrame", background=self.darkBg)

        self.style.configure(
            "TProgressbar", background=self.activeColor, padding=(10, 10, 10, 10))
        self.style.configure(
            "TLabel", background=self.defaultBg, foreground=self.defaultFg)
        self.style.configure(
            "TScale", background=self.defaultBg, foreground=self.defaultFg)

        self.style.map("TScale", troughcolor=[
                       ("!focus", self.genericBg), ("focus", self.focusedColor)])

        self.style.map("TLabel", foreground=[
                       ("!focus", self.defaultFg), ("focus", self.focusedColor)])

        self.style.map("TButton", background=[
                       ("!focus", self.genericBg), ("focus", self.focusedColor)])

        self.style.map("TSpinbox", fieldbackground=[
                       ("!focus", self.defaultFg), ("focus", self.focusedColor)])

        self.style.configure("Active.TButton",
                             background=self.activeColor, foreground=self.defaultFg)

        self.style.map("Active.TButton", background=[])

        # EVENTS AND SHORTCUTS

        self.bind_class("TScale", "<Button-3>", self.RightPoke)
        self.bind_class("TScale", "<space>", self.RightPoke)
        self.bind("<r>", lambda x: self.Record())
        self.bind("<a>", lambda x: self.AddLocalMike())
        self.bind("<Control-a>", lambda x: self.ToggleServer())
        self.bind("<n>", lambda x: self.takeVar.set(self.takeVar.get() + 1))
        self.bind("<Control-n>", lambda x: self.NewScene())
        self.bind("<o>", lambda x: self.OpenMixedRecording())
        self.bind("<Control-o>", lambda x: self.OpenFolder())
        self.bind("<m>", lambda x: self.SetListen("muted"))
        self.bind("<Control-m>", lambda x: self.AskChangeOutput())

        audiohost.cbOnMikeNew = self.OnNewMike
        audiohost.cbOnMikeDisconnect = self.OnMikeDisconnect
        audiohost.cbOnMikeData = self.OnMikeGotData

        self.protocol("WM_DELETE_WINDOW", self.OnClose)

    def NewScene(self):
        self.sceneVar.set(self.sceneVar.get() + 1)
        self.takeVar.set(1)

    def UpdateStats(self):
        if(self.isRecording):
            tm = datetime.datetime.now() - self.recStartTime
            dr = divmod(tm.total_seconds(), 60)

            minutes = round(dr[0])
            seconds = round(dr[1])
            size = f"{asizeof.asizeof(self.recBuffer)/1000:.2f}"
            self.recTime.set(
                f"T: {str(minutes).zfill(3)}:{str(seconds).zfill(2)} M: {size.zfill(6)} KB")
        else:
            self.recTime.set("Powodzenia z nagrywaniem!")

    def OpenFolder(self):
        if(os.path.isdir(self.GetFolder())):
            subprocess.Popen(["xdg-open", self.GetFolder()])
        else:
            messagebox.showinfo(
                "Brak folderu", "To ujęcie jeszcze nie zostało nagrane.")

    def OpenMixedRecording(self):
        if(os.path.isdir(self.GetFolder())):
            subprocess.Popen(
                ["xdg-open", f"{self.GetFolder()}/audio_{self.sceneVar.get()}_mix.wav"])
        else:
            messagebox.showinfo(
                "Brak folderu", "To ujęcie jeszcze nie zostało nagrane.")

    def GetFolder(self):
        return f"recordings/S{self.sceneVar.get()}_PART{self.partVar.get()}_{self.takeVar.get()}"

    def SetAmplify(self, mikeId, value):
        audiohost.playbackVolumes[mikeId] = float(value)

    def UserChangeLabel(self, mikeId):
        value = simpledialog.askstring(
            "Zmień nazwę", f"Podaj nową nazwę dla {audiohost.GetMikeName(mikeId)}:", initialvalue=audiohost.GetMikeName(mikeId))
        if value is not None:
            if not util.is_alphanumeric(value):
                messagebox.showerror("Błąd", "Nieprawidłowa nazwa!")
                return
            audiohost.mikeLabels[mikeId] = value
            audiohost.ReloadMic(mikeId)

    def AskChangeOutput(self):
        dc = audiohost.audio.get_device_count()
        lis = []
        for i in range(dc):
            dev = audiohost.audio.get_device_info_by_index(i)
            lis.append(f"{i} : {dev['name']}")

        outId = customcompo.ComboDialog(
            self, "Ustaw wyjście", lis).getresult()
        if outId is None:
            return
        if not audiohost.SetOutputDevice(outId):
            messagebox.showerror("Błąd", "Nie udało się połączyć wyjścia.")

    def SetListen(self, mikeId):
        if mikeId == "muted":
            for i in audiohost.playbackEnabled.keys():
                audiohost.playbackEnabled[i] = False
        else:
            audiohost.playbackEnabled[mikeId] = not audiohost.playbackEnabled[mikeId]

        keys = list(self.mikePanels.keys())
        for mike in keys:
            panel = self.mikePanels[mike]
            if audiohost.playbackEnabled[mike]:
                panel.winfo_children()[2].configure(
                    text="Słuchanie", style="Active.TButton")
            else:
                panel.winfo_children()[2].configure(
                    text="Słuchaj", style="TButton")

    def RemoveMic(self, mikeId):
        audiohost.RemoveMike(mikeId)

    def RecStop(self, user=True):
        self.isRecording = False
        folder = self.GetFolder()
        if not os.path.isdir(folder):
            os.mkdir(folder)
        else:
            shutil.rmtree(folder)
            os.mkdir(folder)

        def write_wave(n, v):
            f = wave.open(
                f"{folder}/audio_{self.sceneVar.get()}_{n}.wav", "wb")
            f.setnchannels(audiohost.CHANNELS)
            f.setsampwidth(audiohost.audio.get_sample_size(audiohost.FORMAT))
            f.setframerate(audiohost.RATE)

            f.writeframes(b"".join(v))
            f.close()

        # write all the saved data to wave files and use pyDub to create a mixed file
        mix = None
        for w in self.recBuffer.keys():
            mn = audiohost.GetMikeName(w)
            write_wave(mn, self.recBuffer[w])

            if mix is None:
                mix = AudioSegment.from_wav(
                    f"{folder}/audio_{self.sceneVar.get()}_{mn}.wav")
            else:
                mix = mix.overlay(AudioSegment.from_wav(
                    f"{folder}/audio_{self.sceneVar.get()}_{mn}.wav"))

        mix.export(f"{folder}/audio_{self.sceneVar.get()}_mix.wav")

        # self.takeVar.set(self.takeVar.get() + 1)
        self.whlScene.configure(state=tk.NORMAL)
        self.whlTake.configure(state=tk.NORMAL)
        self.bgImg.config(image=self.iconBg)
        self.btnRecord.configure(
            text="Nagraj (R)", style="TButton")

    def RecStart(self):

        folder = self.GetFolder()

        if(os.path.isdir(folder)):
            q = messagebox.askyesnocancel(
                "Uwaga", "Na pewno nadpisać istniejące nagranie?")
            if q == False:
                while os.path.isdir(folder):
                    self.takeVar.set(self.takeVar.get() + 1)
                    folder = self.GetFolder()
                os.mkdir(folder)
                messagebox.showinfo("Informacja",
                                    "Nagranie zostanie zapisane jako TAKE " + str(self.takeVar.get()))
            elif q == None:
                return

        self.isRecording = True
        self.recStartTime = datetime.datetime.now()

        self.recBuffer = {}
        for w in audiohost.connectedMikes.keys():
            self.recBuffer[w] = []

        self.whlScene.configure(state=tk.DISABLED)
        self.whlTake.configure(state=tk.DISABLED)
        self.bgImg.configure(image=self.iconBgRec)

        self.btnRecord.configure(
            text="Stop (R)", style="Active.TButton")

    def Record(self):
        if(len(audiohost.connectedMikes) == 0):
            messagebox.showerror("Brak mikrofonów", "Nie wykryto mikrofonów.")
            return

        if not os.path.isdir("recordings"):
            os.mkdir("recordings")

        if self.isRecording:
            self.RecStop()
        else:
            self.RecStart()

    def RightPoke(self, event):
        mn = event.widget.cget("from")
        mx = event.widget.cget("to")
        val = simpledialog.askfloat(
            "Edytuj", f"Podaj wartość <{mn}-{mx}>", minvalue=mn, maxvalue=mx, initialvalue=event.widget.get())
        if val is not None:
            event.widget.set(val)

    def OnClose(self):
        global serverThread

        if(serverThread is not None or self.isRecording):
            if messagebox.askokcancel("Wyjście", "Na stówke byq?"):
                if self.isRecording:
                    self.RecStop(False)
                    messagebox.showwarning(
                        "Uwaga", "Wyłączono nagrywanie!")
            else:
                return False

        audiohost.Shutdown()
        self.SaveData()
        self.destroy()
        print("Прощай на веки, последняя любовь")

    def SetMikeCount(self, count):
        self.mikesCount.set("Połączone mikrofony: " + str(count))

    def OnNewMike(self, mikeId):
        if self.isRecording:
            self.RecStop(False)
            messagebox.showwarning(
                "Uwaga", "Podłączono nowy mikrofon więc przerwano nagrywanie.")

        self.SetMikeCount(len(audiohost.connectedMikes))
        frm = ttk.Frame(self.pnlMikes)
        frm.pack(side=TOP, fill=tk.X)

        lbl = ttk.Label(frm, text=audiohost.GetMikeName(
            mikeId), width=14, takefocus=1)
        lbl.bind("<Button-3>", lambda e: self.UserChangeLabel(mikeId))
        lbl.bind("<space>", lambda e: self.UserChangeLabel(mikeId))
        lbl.pack(side=LEFT)

        pgb = ttk.Progressbar(frm, orient=tk.HORIZONTAL)
        pgb.pack(side=LEFT, fill=tk.X, expand=True)
        pgb.configure(value=1)

        btnLsn = ttk.Button(frm, image=self.iconSpeaker, command=lambda: self.SetListen(
            mikeId))
        btnLsn.pack(side=RIGHT, padx=(0, 0))

        btnCls = ttk.Button(frm, image=self.iconBin, command=lambda: self.RemoveMic(
            mikeId), width=2)
        btnCls.pack(side=RIGHT, padx=(5, 0))

        sld = ttk.Scale(frm, from_=0, to=400, orient=tk.HORIZONTAL,
                        command=lambda v: self.SetAmplify(mikeId, v), value=50, length=150)
        sld.pack(side=RIGHT, padx=(5, 0))

        sld.set(audiohost.playbackVolumes[mikeId])
        self.mikePanels[mikeId] = frm

    def OnMikeDisconnect(self, mikeId):
        if self.isRecording:
            self.RecStop(False)
            messagebox.showwarning(
                "Uwaga", "Odłączono mikrofon więc przerwano nagrywanie.")
        self.SetMikeCount(len(audiohost.connectedMikes))
        m = self.mikePanels[mikeId]
        self.mikePanels.pop(mikeId)
        m.destroy()

    def OnMikeGotData(self, mikeId, data):

        # a sort of a main loop architecture
        delta = datetime.datetime.now() - self.lastCheck
        if(delta.total_seconds() > 1):
            self.UpdateStats()
            self.lastCheck = datetime.datetime.now()

        if self.isRecording:
            self.recBuffer[mikeId].append(data)

        rms = audioop.rms(data, 1)
        R = 10**(rms/20)
        try:
            bar = self.mikePanels[mikeId].winfo_children()[1]
            bar.configure(value=R*0.1)
        except Exception:
            print("oops! mirophone no longer is here but we tried to update it")

    def AddLocalMike(self):
        dc = audiohost.audio.get_device_count()
        lis = []
        for i in range(dc):
            dev = audiohost.audio.get_device_info_by_index(i)
            lis.append(f"{i} : {dev['name']}")

        mikeId = customcompo.ComboDialog(
            self, "Dodaj mikrofon", lis).getresult()
        if mikeId is None:
            return
        if not audiohost.CreateLocalStream(mikeId):
            messagebox.showerror("Błąd", "Nie udało się połączyć mikrofonu.")

    def ToggleServer(self):
        if self.isRecording:
            self.RecStop(False)

        global serverThread
        if serverThread is None:
            serverThread = threading.Thread(target=audiohost.StartServer)
            serverThread.start()
            self.btnStart.config(text="Zatrzymaj TCP (^A)",
                                 style="Active.TButton")
        else:
            audiohost.StopServer()
            self.btnStart.config(text="Wystartuj TCP (^A)", style="TButton")
            serverThread = None

    def SaveData(self):
        d = {
            "scene": self.sceneVar.get(),
            "take": self.takeVar.get(),
            "amplifiers": audiohost.playbackVolumes,
            "labels": audiohost.mikeLabels,
            "output": audiohost.outputDevice
        }
        f = open("last.data", "w")
        f.write(json.dumps(d))
        f.close()

    def LoadData(self):
        if not os.path.isfile("last.data"):
            return

        f = open("last.data", "r")
        d = json.loads(f.read())
        f.close()
        self.sceneVar.set(d["scene"])
        self.takeVar.set(d["take"])
        audiohost.playbackVolumes = d["amplifiers"]
        audiohost.mikeLabels = d["labels"]
        audiohost.outputDevice = d["output"]


if __name__ == "__main__":
    app = App()
    app.mainloop()

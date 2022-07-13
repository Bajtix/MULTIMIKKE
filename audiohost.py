
from glob import glob
import socket
import selectors
import threading
import types
from numpy import full
import pyaudio
import time
import audioop

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096


connectedMikes = {}
mikeLabels = {}

playbackBuffers = {}

audio = None
outputStream = None
selector = None
serverSocket = None
serverRunning = False

generalRunning = True

__playbackThread = None

outputDevice = 0
localStreams = {}


def cbOnMikeNew(mikeId): return None
def cbOnMikeDisconnect(mikeId): return None
def cbOnMikeData(mikeId, data): return None


def Init():
    global audio, outputStream, generalRunning, __playbackThread
    audio = pyaudio.PyAudio()
    for i in range(0, audio.get_device_count()):
        dev = audio.get_device_info_by_index(i)
        print(f"{i} : {dev['name']}")

    outputStream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                              frames_per_buffer=CHUNK, output_device_index=outputDevice)

    generalRunning = True
    __playbackThread = threading.Thread(target=__Playback)
    __playbackThread.start()


def SetOutputDevice(index):
    global outputStream, outputDevice
    try:
        outputStream.stop_stream()
        outputStream.close()
        outputStream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                                  frames_per_buffer=CHUNK, output_device_index=index)
        outputDevice = index
        outputStream.start_stream()

        return True
    except OSError:
        print("Error: Output device could not be set")
        return False


def StopServer():
    global serverRunning, connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    mikes = list(connectedMikes.keys())
    for w in mikes:
        if connectedMikes[w] is not None:
            Disconnect(w)
    serverRunning = False


# Shuts the whole thing down
def Shutdown():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream, generalRunning

    StopServer()
    for w in connectedMikes.keys():
        RemoveMike(w)
    serverRunning = False
    generalRunning = False

    outputStream.close()
    audio.terminate()

    connectedMikes = {}
    print("Shutting down...")


def __StopServer():

    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    selector.close()

    print("MIKKE TCP SERVER STOPPING...")
    serverSocket.close()
    serverSocket = None
    serverRunning = False
    print("MIKKE TCP SERVER STOPPED!")


def GetIdFromSocket(sock):
    host, port = sock.getpeername()
    return host.split(".")[-1]


def ReloadMic(mikeId):
    cbOnMikeDisconnect(mikeId)
    cbOnMikeNew(mikeId)


def GetMikeName(mikeId):
    if mikeId in mikeLabels:
        return mikeLabels[mikeId]
    return f"MIC ({mikeId})"


def Disconnect(mikeId):
    sock = connectedMikes[mikeId]

    print("Connection to ", sock.getpeername(), " is closing...")
    selector.unregister(sock)
    connectedMikes.pop(mikeId)
    sock.close()
    cbOnMikeDisconnect(mikeId)


def StartServer():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(("", 4200))
    serverSocket.listen()
    serverSocket.setblocking(False)

    print("MIKKE TCP SERVER LISTENING...")

    selector = selectors.DefaultSelector()

    selector.register(serverSocket, selectors.EVENT_READ, data=None)

    serverRunning = True

    def AcceptConnection(sck):
        global serverRunning, cbOnMikeNew

        if not serverRunning:
            return

        global connectedMikes
        mikeSocket, address = serverSocket.accept()
        mikeSocket.setblocking(False)
        print("New connection from ", address)

        try:
            print(connectedMikes[GetIdFromSocket(mikeSocket)])
            print("The microphone is NOT new...")
            cbOnMikeDisconnect(GetIdFromSocket(mikeSocket))
        except KeyError:
            print("The microphone is new...")

        connectedMikes[GetIdFromSocket(mikeSocket)] = mikeSocket

        cbOnMikeNew(GetIdFromSocket(mikeSocket))

        # register a selector for that connection
        data = types.SimpleNamespace(addr=address, inb=b"", outb=b"")
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        selector.register(mikeSocket, events, data=data)

    def ReadConnection(k, m):
        global serverRunning

        if not serverRunning:
            return

        sock = k.fileobj
        data = k.data

        mikeId = GetIdFromSocket(sock)

        if mask & selectors.EVENT_READ:
            receivedData = sock.recv(CHUNK)
            if receivedData:
                # data.outb += receivedData
                cbOnMikeData(mikeId, receivedData)
            else:
                Disconnect(mikeId)

    try:
        while serverRunning:
            events = selector.select(timeout=1)

            for key, mask in events:
                if key.data is None:
                    AcceptConnection(key.fileobj)
                else:
                    ReadConnection(key, mask)
    except KeyboardInterrupt:
        pass
    __StopServer()


def CreateLocalStream(dev):
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream
    connectedMikes[f"L{dev}"] = None

    def LocalStreamCallback(in_data, frame_count, time_info, status):
        cbOnMikeData(f"L{dev}", in_data)
        return (None, pyaudio.paContinue)
    try:
        localStreams[f"L{dev}"] = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                                             output=False, frames_per_buffer=CHUNK, input_device_index=dev, stream_callback=LocalStreamCallback)
        cbOnMikeNew(f"L{dev}")
        return True
    except OSError:
        print("Failed to open local stream")
        connectedMikes.pop(f"L{dev}")
        return False


def RemoveLocalStream(mikeId):
    localStreams[mikeId].close()
    localStreams.pop(mikeId)
    connectedMikes.pop(mikeId)
    cbOnMikeDisconnect(mikeId)


def RemoveMike(mikeId):
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream
    if not mikeId in connectedMikes:
        return
    if connectedMikes[mikeId] is not None:
        Disconnect(mikeId)
    else:
        RemoveLocalStream(mikeId)


def BufferMikeData(mikeId, data):
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream, playbackBuffers
    if not mikeId in playbackBuffers.keys():
        playbackBuffers[mikeId] = []
        return

    if playbackBuffers[mikeId] is None:
        playbackBuffers[mikeId] = []

    dArr = []
    for d in data:
        dArr.append(d)
    playbackBuffers[mikeId] = playbackBuffers[mikeId] + dArr


def __Playback():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream, currentFrameBuffer, generalRunning, playbackBuffers
    while generalRunning:
        keys = list(playbackBuffers.keys())
        for mikeId in keys:
            if playbackBuffers[mikeId] is None:
                continue

            if len(playbackBuffers[mikeId]) > 8192:
                frameData = playbackBuffers[mikeId][:4096]
                playbackBuffers[mikeId] = playbackBuffers[mikeId][4096:]
                bs = bytes(frameData)
                outputStream.write(bs)

        time.sleep(1/RATE * CHUNK / 2)


if __name__ == "__main__":
    StartServer()

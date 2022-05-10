
from glob import glob
import socket
import selectors
import types
import pyaudio

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096

PLAYBACK_DEVICE = 36

connectedMikes = {}
mikeLabels = {}
audio = None
outputStream = None
selector = None
serverSocket = None
running = False

localStreams = {}


def cbOnMikeNew(mikeId): return None
def cbOnMikeDisconnect(mikeId): return None
def cbOnMikeData(mikeId, data): return None


def Init():
    global audio, outputStream
    audio = pyaudio.PyAudio()
    for i in range(0, audio.get_device_count()):
        dev = audio.get_device_info_by_index(i)
        print(f"{i} : {dev['name']}")

    outputStream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                              frames_per_buffer=CHUNK)


def Stop():
    global running, connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    mikes = list(connectedMikes.keys())
    for w in mikes:
        print("Stopping server, removing mike ", w)
        if not "L" in w:
            Disconnect(w)
    running = False


# Shuts the whole thing down
def Shutdown():
    global connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream
    Stop()
    for w in connectedMikes.keys():
        RemoveMike(w)
    outputStream.close()
    audio.terminate()
    connectedMikes = {}


def __Stop():

    global connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    selector.close()

    print("MIKKE TCP SERVER STOPPING...")
    serverSocket.close()
    serverSocket = None
    running = False
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


def Run():
    global connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(("", 4200))
    serverSocket.listen()
    serverSocket.setblocking(False)

    print("MIKKE TCP SERVER LISTENING...")

    selector = selectors.DefaultSelector()

    selector.register(serverSocket, selectors.EVENT_READ, data=None)

    running = True

    def AcceptConnection(sck):
        global running, cbOnMikeNew

        if not running:
            return

        global connectedMikes
        mikeSocket, address = serverSocket.accept()
        mikeSocket.setblocking(False)
        print("New connection from ", address)
        connectedMikes[GetIdFromSocket(mikeSocket)] = mikeSocket

        cbOnMikeNew(GetIdFromSocket(mikeSocket))

        # register a selector for that connection
        data = types.SimpleNamespace(addr=address, inb=b"", outb=b"")
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        selector.register(mikeSocket, events, data=data)

    def ReadConnection(k, m):
        global running

        if not running:
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
        while running:
            events = selector.select(timeout=1)

            for key, mask in events:
                if key.data is None:
                    AcceptConnection(key.fileobj)
                else:
                    ReadConnection(key, mask)
    except KeyboardInterrupt:
        pass
    __Stop()


def CreateLocalStream(dev):
    global connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream
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
    global connectedMikes, audio, outputStream, selector, serverSocket, running, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream
    if not mikeId in connectedMikes:
        return
    if connectedMikes[mikeId] is not None:
        Disconnect(mikeId)
    else:
        RemoveLocalStream(mikeId)


if __name__ == "__main__":
    Run()

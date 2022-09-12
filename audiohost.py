
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
PLAYBACK_CHUNK = 8192


connectedMikes = {}
mikeLabels = {}
playbackBuffers = {}
playbackEnabled = {}
playbackVolumes = {"main": 50}

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

    SetOutputDevice(outputDevice)

    generalRunning = True
    __playbackThread = threading.Thread(target=__Playback)
    __playbackThread.start()


def SetOutputDevice(index):
    global outputStream, outputDevice, playbackBuffers
    try:
        if outputStream is not None:
            outputStream.stop_stream()
            outputStream.close()
            outputStream = None
        outputStream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True,
                                  frames_per_buffer=PLAYBACK_CHUNK, output_device_index=index)
        outputDevice = index
        outputStream.start_stream()
        playbackBuffers = {}

        return True
    except OSError:
        print("Error: Output device could not be set")
        return False


def IsLocalMike(mikeId):
    return mikeId.strip().startswith("L")


def StopServer():
    global serverRunning, connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    if not serverRunning:
        return

    print("Disconnecting all TCP...")
    mikes = list(connectedMikes.keys())
    for w in mikes:
        if not IsLocalMike(w):
            RemoveMike(w)
    serverRunning = False


# Shuts the whole thing down
def Shutdown():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream, generalRunning
    print("Shutting down...")
    StopServer()
    BufferClear()
    print("Removing all mikes...")
    keys = list(connectedMikes.keys())
    for w in keys:
        RemoveMike(w)
    connectedMikes = {}
    serverRunning = False
    generalRunning = False

    outputStream.close()
    audio.terminate()
    print("Terminated audiohost")


def EnablePlayback(mikeId):
    global playbackBuffers, playbackEnabled
    playbackEnabled[mikeId] = True


def DisablePlayback(mikeId):
    global playbackBuffers, playbackEnabled
    playbackEnabled[mikeId] = False
    playbackBuffers[mikeId] = None


def IsPlayback(mikeId):
    global playbackBuffers, playbackEnabled
    return mikeId in playbackEnabled and playbackEnabled[mikeId]


def __StopServer():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData
    selector.close()

    serverSocket.close()
    serverSocket = None
    serverRunning = False
    print("TCP socket closed")


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

    if serverRunning:
        return

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(("", 4200))
    serverSocket.listen()
    serverSocket.setblocking(False)

    print("TCP Server starting...")

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

        mikeId = GetIdFromSocket(mikeSocket)

        try:
            print(connectedMikes[mikeId])
            print("The microphone is NOT new...")
            cbOnMikeDisconnect(mikeId)
        except KeyError:
            print("The microphone is new...")

        connectedMikes[mikeId] = mikeSocket

        if mikeId not in playbackVolumes:
            playbackVolumes[mikeId] = 50

        playbackEnabled[mikeId] = False

        cbOnMikeNew(GetIdFromSocket(mikeSocket))

        # register a selector for that connection
        data = types.SimpleNamespace(addr=address, inb=b"", outb=b"")
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        selector.register(mikeSocket, events, data=data)

        BufferClear()

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
                try:
                    receivedData = audioop.mul(
                        receivedData, audio.get_sample_size(FORMAT), (float(playbackVolumes[mikeId])*float(playbackVolumes["main"]))/10000.0)
                    BufferMikeData(mikeId, receivedData)
                except:
                    print("Ouch! Received data was fucked up")
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
    mikeId = f"L{dev}"
    connectedMikes[mikeId] = None

    def LocalStreamCallback(in_data, frame_count, time_info, status):
        cbOnMikeData(mikeId, in_data)
        try:
            receivedData = audioop.mul(
                in_data, audio.get_sample_size(FORMAT), (float(playbackVolumes[mikeId])*float(playbackVolumes["main"]))/10000.0)
            BufferMikeData(mikeId, receivedData)
        except:
            print("Ouch! Local data was fucked up!")
        
        return (None, pyaudio.paContinue)
    try:
        localStreams[mikeId] = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True,
                                          output=False, frames_per_buffer=CHUNK, input_device_index=dev, stream_callback=LocalStreamCallback)
        if mikeId not in playbackVolumes:
            playbackVolumes[mikeId] = 50
        playbackEnabled[mikeId] = False

        cbOnMikeNew(mikeId)
        return True
    except OSError:
        print("Failed to open local stream")
        connectedMikes.pop(mikeId)
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
    print("Removing microphone", mikeId)
    BufferClear()
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


def BufferClear():
    global playbackBuffers
    playbackBuffers = {}


def __Playback():
    global connectedMikes, audio, outputStream, selector, serverSocket, serverRunning, cbOnMikeNew, cbOnMikeDisconnect, cbOnMikeData, localStream, currentFrameBuffer, generalRunning, playbackBuffers
    while generalRunning:
        keys = list(playbackBuffers.keys())
        mix = None
        for mikeId in keys:
            if playbackBuffers[mikeId] is None:
                continue

            if len(playbackBuffers[mikeId]) > PLAYBACK_CHUNK:
                frameData = playbackBuffers[mikeId][:PLAYBACK_CHUNK]
                playbackBuffers[mikeId] = playbackBuffers[mikeId][PLAYBACK_CHUNK:]
                bs = bytes(frameData)
                if playbackEnabled[mikeId] == False:
                    continue
                if mix is None:
                    mix = bs
                else:
                    mix = audioop.add(mix, bs, audio.get_sample_size(FORMAT))
        if mix is not None and outputStream is not None:
            outputStream.write(mix)
        time.sleep(1/RATE * PLAYBACK_CHUNK / 2)
    print("Playback stopped")


if __name__ == "__main__":
    StartServer()

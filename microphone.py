import socket
from time import sleep
import pyaudio


FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096

SERVER_ADDR = ("192.168.0.24", 4200)

connected = False
quit = False

print("WELCOME TO MIKKE MIKE!")

while not quit:

    audio = pyaudio.PyAudio()
    clientSocket = None

    print("ATTEMPTING A CONNECTION TO ", SERVER_ADDR)
    while not connected:
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            clientSocket.connect(SERVER_ADDR)
            connected = True

        except:
            try:
                sleep(5)
                print("MIKKE MIKE NOT CONNECTED... SLEEPING...")
            except KeyboardInterrupt:
                quit = True
                exit()

    print("MIKKE MIKE CONNECTED TO " + str(SERVER_ADDR))

    def MikeCallback(in_data, frame_count, time_info, status):
        clientSocket.send(in_data)
        return (None, pyaudio.paContinue)

    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK, stream_callback=MikeCallback)

    print("MIKE ON AIR!")

    try:
        while connected:
            # nothing
            sleep(0.5)
    except KeyboardInterrupt:
        quit = True
    except (BrokenPipeError, ConnectionResetError):
        print("MIKKE SERVER TOLD US TO GO FRICK OURSELVES!")
        pass

    connected = False
    stream.stop_stream()
    stream.close()
    audio.terminate()
    print("RECORDING STOPPED")

    clientSocket.close()
    print("MIKKE MIKE DISCONNECTED")

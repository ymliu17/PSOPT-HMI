import requests
import json
import time
import biosignalHeartpy_v002 as bio
import pandas as pd
import threading
import os
import numpy as np
import gc
import platform
import sys
import argparse
from contextlib import nullcontext
from ecg_monitor import enabled_monitor, publish as _publish_ecg_monitor


def _plux_directory():
    """Choose the bundled extension for the running Python ABI and CPU."""
    from pathlib import Path

    pyver = f"{sys.version_info.major}{sys.version_info.minor}"
    system = platform.system()
    if system == "Darwin":
        folder = f"M1_{pyver}" if platform.machine().lower() in ("arm64", "aarch64") else f"MacOS/Intel{pyver}"
    elif system == "Windows":
        folder = f"Win{64 if sys.maxsize > 2**32 else 32}_{pyver}"
    elif system == "Linux":
        folder = "Linux64"
    else:
        raise RuntimeError(f"Unsupported PLUX platform: {system}")
    return Path(__file__).resolve().parent / "PLUX-API-Python3" / folder


plux_directory = _plux_directory()
if not plux_directory.is_dir():
    raise RuntimeError(
        f"No bundled PLUX driver for this Python/CPU: {plux_directory}. "
        "Use a Python version and architecture matching a bundled PLUX driver."
    )
print(f"PLUX driver: {plux_directory}")
sys.path.insert(0, str(plux_directory))

import plux

class NewDevice(plux.SignalsDev):
    stopAcquisition = False

    def __init__(self, address):
        # PLUX consumes address in its native __new__. SignalsDev.__init__ is
        # object.__init__, so passing address to it raises TypeError.
        self.duration = 0
        self.frequency = 0
        self.stopAcquisition = False

    def onRawFrame(self, nSeq, data):  # onRawFrame takes three arguments
        #print(nSeq, *data)
        dataList.append([nSeq, *data]) #store the raw data
        return self.stopAcquisition

    def onInterrupt(self, param):
        print("Received request to stop ECG acquisition")
        self.stopAcquisition = True
        return True

ECG_DEVICES = ["BTH00:07:80:0F:31:54", "BTH00:07:80:0F:30:9F", "BTH00:07:80:0F:31:34"]
# ecg_device= "BTH00:07:80:0F:31:54" #ECG address - Stanford
# ecg_device2= "BTH00:07:80:0F:30:9F" #ECG address - Rochester


code=0x03
if isinstance(code, str):
    code = int(code, 16)
    

# Signal parameters
frequency=1000

r_threshold = 0.2
shapA_List = []
shapB_List = []
raw_List = []
requestTime = 0.5
webserver = "https://brainwellnessgamesapi.azurewebsites.net"

def loopDeviceThread(deviceToLoop):
    # while isGameReady == True:
    print("Starting acquisition...")
    deviceToLoop.start(deviceToLoop.frequency, code, 16)
    deviceToLoop.stopAcquisition = False
    deviceToLoop.loop()
    deviceToLoop.stop()
    print("ECG device is now stopped")


def connectToDevice():
    ecgReady_statement = False
    while ecgReady_statement == False:
        available_Device = plux.SignalsDev.findDevices()
        print("Available Devices: ", end="")
        print(available_Device)

        if len(available_Device) > 0:
            for ECG_device in ECG_DEVICES:
                if (ECG_device in available_Device[0]):
                    print("ECG available")
                    device = NewDevice(ECG_device)
                    # A native constructor can return after printing a timeout.
                    # Verify communication before reporting a usable device.
                    try:
                        device.setTimeout(5000)
                        battery = device.getBattery()
                    except Exception:
                        try:
                            device.close()
                        except Exception:
                            pass
                        raise
                    print(f"Connected to ECG device {ECG_device}; battery: {battery:.2f}%", flush=True)
                    if battery < 10:
                        print("Low ECG battery: recharge the device before a recording session.", flush=True)
                    device.frequency = int(frequency)
                    ecgReady_statement = True
                    break
        elif len(available_Device) == 0:
            print("Check that the device is on")
        time.sleep(0.5)
    return device

def _run_session(sessionExternalId):
    global dataList
    print(sessionExternalId)
    session_getIdentifier_api_url = "{}/session/GetByExternalIdentifier?externalIdentifier={}".format(webserver, sessionExternalId)

    # We are requesting the latest session Identifier associated with the externalIdentifier above
    identifierResponse = requests.get(session_getIdentifier_api_url)

    print(identifierResponse.json()) # This is just for debug
    print(identifierResponse.status_code) #It's good practice to to check if this is a 200 or 201

    # This is the UniqueId for this session
    sessionId = identifierResponse.json()["identifier"]

    # URL to get Update the Status of the ECG Device
    ecg_updateStatus_api_url = "{}/device/UpdateStatus".format(webserver)

    # URL to get Save the Result of the ECG Device
    ecg_saveResult_api_url = "{}/device/SaveResult".format(webserver)

    # DEBUG -- To check the sessionId in the database, or making requests to the API
    print(sessionId)

    # URL to get the current Block of a specific Session
    block_getLatestForSession_api_url = "{}/block/GetLatestForSession?sessionIdentifier={}".format(webserver, sessionId)

    game_ready_api_url = "https://brainwellnessgamesapi.azurewebsites.net/game/checkstatus?sessionId={}".format(sessionId)

    ecgReady_statement = False
    device = connectToDevice()
    number_blocks = 0



    while True:
        print("This is the beginning of a Block")
        number_blocks =  number_blocks + 1
        print("BLOCK NUMBER " + str(number_blocks))
        dataList = []
        latestBlockResponse = requests.get(block_getLatestForSession_api_url)

        #DEBUG
        print(latestBlockResponse.json())
        #print(latestBlockResponse.status_code) #It's good practice to to check if this is a 200 or 201

        # UniqueIdentifier of the current Block
        blockId = latestBlockResponse.json()["identifier"]

        # URL to check the Status of the Game for the current Block --> CT TODO: sessionId in the URL needs to be updated...
        game_checkStatus_api_url = "{}/game/checkstatus?sessionId={}".format(webserver, blockId)

        gameReadyResponse = requests.get(game_checkStatus_api_url)
        #print(gameReadyResponse.json())
        if (gameReadyResponse.status_code == 200):
            print("Waiting for game to start...", end ='', flush=True)
        else:
            print("Something went wrong checking if the game was ready")
            print("Checking again...")
        #print(gameReadyResponse.status_code) #It's good practice to to check if this is a 200 or 201

        # Tells us if the game is currently Ready
        isGameReady = gameReadyResponse.json()["isGameReady"]

        # Loop until the game is ready
        while isGameReady == False:
            gameReadyResponse = requests.get(game_checkStatus_api_url)
            print(".", end ='', flush=True)
            #print(gameReadyResponse.json())
            #print(gameReadyResponse.status_code) #It's good practice to to check if this is a 200 or 201
            isGameReady = gameReadyResponse.json()["isGameReady"]
            time.sleep(requestTime)    
        print("")

        print("Game is ready:", isGameReady)

        ecgReady_statement = False

        while ecgReady_statement == False:
            #Let's try this for now
            if (device.getBattery() > 0):
                print("ECG available")
                ecgReady_statement = True
                ecgReady = {"isReady": True, "sessionIdentifier": "{}".format(blockId)}
                ecgReadyResponse = requests.put(ecg_updateStatus_api_url, json=ecgReady)
            
                if (ecgReadyResponse.status_code == 200):
                    print("Notified game that ECG is ready")
                else:
                    print("Something went wrong notifying the game that the ECG is ready")    

                #print(ecgReadyResponse.status_code) #It's good practice to to check if this is a 200 or 201
            else :
                print("Lost connection to device. Check that the device is on")
                ecgReady = {"isReady": False, "sessionIdentifier": "{}".format(blockId)}
                ecgReadyResponse = requests.put(ecg_updateStatus_api_url, json=ecgReady)
                device = connectToDevice()
                time.sleep(0.5)

        device.stopAcquisition = False
        _publish_ecg_monitor("begin", block=blockId, number=number_blocks,
                             frequency=frequency, threshold=r_threshold,
                             shapelet_a=bio.shapeletA, shapelet_b=bio.shapeletB)
        print("Start ECG acquisition")
    
        loopThread = threading.Thread(target = loopDeviceThread, args=(device,))
        loopThread.daemon = True
        loopThread.start()
    

        print("Playing", end ="", flush=True)
        while isGameReady == True:
            print(".", end ="", flush=True) 
            # ff = pd.DataFrame([item[2] for item in dataList])#,columns=['nseq', 'ECG'])
            # ff.to_csv(csv_name)
            _publish_ecg_monitor("samples", rows=dataList)
            time.sleep(1) #0.5
            gameReadyResponse = requests.get(game_checkStatus_api_url)
            isGameReady = gameReadyResponse.json()["isGameReady"]
            time.sleep(requestTime)
    
        print("")
        print("User completed the block, stopping ECG device")
        # Game is no longer Ready so the user stopped playing. Now we can stop ECG device and do computations
        #device.stopAcquisition = True
        device.interrupt(True)

        #print("Calling device stop")
        # device.stop()
        #print("Calling device close")
        #device.close()
    
        time.sleep(5)
        raw_signal = pd.DataFrame(dataList)
    
        # Change ECG status to notReady
        ecgReady = {"isReady": False, "sessionIdentifier": "{}".format(blockId)}
        ecgReadyResponse = requests.put(ecg_updateStatus_api_url, json=ecgReady)

        # print(ecgReadyResponse.json())
        # print(ecgReadyResponse.status_code) #It's good practice to to check if this is a 200 or 201
        if (ecgReadyResponse.status_code == 200):
            print("Notified game that ECG device is computing")
        else:
            print("Something went wrong notifying the game that the ECG device is computing") 
    

        # ECG computations on API

        raw_ecg_data = np.asarray(raw_signal[2])
        _publish_ecg_monitor("processing", raw=raw_ecg_data)
        # Save raw ECG data to csv
        bio.saveECG(raw_ecg_data, sessionExternalId, blockId)

        # Invert the signal if needed and clean it
        # This is now embedded in the getHF_HRV function below
        #clean_RawSignal = bio.getCleanECGSignal(raw_ecg_data) 

        # Get HF HRV values
        hrv_hf_values = bio.getHF_HRV(raw_ecg_data, sessionExternalId, blockId) #get HF

        shapA, shapB = bio.compareShapelets(hrv_hf_values) #compare HF values with shapelets
        bio.saveRho(shapA, 'A', sessionExternalId, blockId)
        bio.saveRho(shapB, 'B', sessionExternalId, blockId)
        #shapA_List.append(shapA)
        #shapB_List.append(shapB)

        if (shapA.rho[0] >= r_threshold)  or (shapB.rho[0] >= r_threshold):
            print ('rho for shapelet A: ' + str(shapA.rho[0]) + ' rho for shapelet B: ' + str(shapB.rho[0]))
            print('Increase level')
            ecgResult = {"IncreaseDifficulty": True, "BlockIdentifier": "{}".format(blockId)}
        else:
            print ('rho for shapelet A: ' + str(shapA.rho[0]) + ' rho for shapelet B: ' + str(shapB.rho[0]))
            print('Do not increase level')
            ecgResult = {"IncreaseDifficulty": False, "BlockIdentifier": "{}".format(blockId)}

        _publish_ecg_monitor("result", rho_a=shapA.rho[0], rho_b=shapB.rho[0],
                             increase=ecgResult["IncreaseDifficulty"])
        ecgResultResponse = requests.put(ecg_saveResult_api_url, json=ecgResult)
        _publish_ecg_monitor("upload", success=ecgResultResponse.status_code == 200,
                             status_code=ecgResultResponse.status_code)
        time.sleep(1)

        # print(ecgResultResponse.json())
        # print(ecgResultResponse.status_code) #It's good practice to to check if this is a 200 or 201
        if (ecgResultResponse.status_code == 200):
            print("Successfully uploaded ECG device computation")
        else:
            print("Something went wrong uploading the ECG device computation") 

        print("Waiting for game...", end ="", flush=True)
        while isGameReady == False:
            gameReadyResponse = requests.get(game_checkStatus_api_url)
            print(".", end ="", flush=True) 
            #print("Game is not ready. It should be creating a new block for the current session...", gameReadyResponse.json())
            # print(gameReadyResponse.status_code)
            isGameReady = gameReadyResponse.json()["isGameReady"]
            time.sleep(requestTime)
        print("")
    
        # Clear 
        del dataList
        del raw_signal
        del raw_ecg_data
        # del clean_RawSignal
        gc.collect()

        if number_blocks == 25:
            break;

    #bio.saveRhoResults(shapA_List, 'A')
    #bio.saveRhoResults(shapB_List, 'B')
    #bio.saveRawData(raw_List)
    print("And we are done with this session!")


def main():
    parser = argparse.ArgumentParser(description="Run PSOPT HMI ECG acquisition and optional monitoring.")
    parser.add_argument("session_id")
    parser.add_argument("monitor", nargs="?", choices=["monitor"],
                        help="Open a separate ECG and HF-HRV monitoring window")
    args = parser.parse_args()
    context = enabled_monitor(args.session_id) if args.monitor else nullcontext()
    with context:
        try:
            _run_session(args.session_id)
        except BaseException as exc:
            _publish_ecg_monitor("error", message=str(exc) or type(exc).__name__)
            raise


if __name__ == "__main__":
    main()

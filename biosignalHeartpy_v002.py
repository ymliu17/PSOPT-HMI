"""
@author: Initial version liz_m, revised by Cristiano Tapparello
"""

import numpy as np
import math
import pandas as pd
from scipy import stats as stats_tools

import neurokit2 as nk
import matplotlib.pyplot as plt
from ecg_monitor import publish as _publish_ecg_monitor

shapeletA = [-1.5116833, -0.5682773, 1.46413934, -0.7661631, 0.6143466, 0.12867262, 1.04853951, -0.4095744]
shapeletB = [-2.0847277, -0.2029212, 1.22671969, -0.3026837, 0.37005532, 0.72853974, 0.5283917, -0.2633737]

fs = 1000 #sampling rate of Biosignalplux
lowFreq = .5
highFreq = 20
# Fixed window size and overlap
window_size = 30 #seconds
windows_overlap = 0.55
# Fixed window size and dynamic overlap to get a fixed number of windows
window_length = 30 * fs #samples
num_windows = 8
min_signal_length = 90 * fs #samples

shapelet_size = len(shapeletA)

# Utility function to divide the signal into overlapping windows
def window(a, width = 30000, overlap = 15000, copy = False):
    # print(width)
    # print(overlap)
    sh = (a.size - width + 1, width)
    st = a.strides * 2
    view = np.lib.stride_tricks.as_strided(a, strides = st, shape = sh)[0::overlap]
    if copy:
        return view.copy()
    else:
        return view

# Utility function to divide the signal into num_windows overlapping windows of size window_size
def create_dynamic_windows(signal, window_size, num_windows):
    signal_length = len(signal)
    step_size = (signal_length - window_size) // (num_windows - 1)

    if step_size <= 0:
        raise ValueError("The window size and number of windows are not compatible with the vector length.")

    windows = np.array([signal[i:i + window_size] for i in range(0, signal_length - window_size + 1, step_size)])

    # Adjust the number of windows, in case it slightly deviates due to rounding
    if len(windows) > num_windows:
        windows = windows[:num_windows]

    return windows

#Invert the signal if needed and clean it
def getCleanECGSignal(rawData):
    # Convert points to mV
    data_mV = ((((rawData/np.power(2,16)) - 0.5) * 3) / 1019) * 1000 #ecg manual pdf page 5

    #Check if the ECG signal is inverted
    ecg_inverted, is_inverted = nk.ecg_invert(data_mV, sampling_rate=fs, show=True)
    
    #Clean the ECG signal
    ecg_cleaned = nk.ecg_clean(ecg_inverted, sampling_rate=fs)

    return ecg_cleaned

def getHF_HRV(rawData, session_external_ID, block_ID):

    hrv_hf = []

    # Check if the signal is long enough to be divided into windows
    # otherwise return an empty list
    if len(rawData) < min_signal_length:
        _publish_ecg_monitor("unavailable", message="Fewer than 90 seconds of ECG; HF-HRV unavailable")
        return hrv_hf
    
    # Clean the signal
    ecg_cleaned = getCleanECGSignal(rawData)
    _publish_ecg_monitor("cleaned", signal=ecg_cleaned)

    # Divide the signal into windows with fixed size and overlap
    view_ecg_clean = window(ecg_cleaned, width = window_size * fs, overlap = int((1-windows_overlap) * window_size * fs), copy = False)
    n_windows = view_ecg_clean.shape[0]

    # Divide the signal into windows with dynamic size and overlap
    windows_ecg_clean = create_dynamic_windows(ecg_cleaned, window_length, num_windows)

    # Iterate over the windows to get the HRV_HF
    # fixed windows size and dynamic overlap to get a fixed number of points
    for i in range(num_windows):
        peaks, info = nk.ecg_peaks(windows_ecg_clean[i], sampling_rate=fs, correct_artifacts=True, show=False)
        hrv_indices = nk.hrv(peaks, sampling_rate=fs, show=False)
        ln_HRV_HF = np.log(hrv_indices['HRV_HF'].values[0])
        hrv_hf.append(ln_HRV_HF)
        step_size = (len(ecg_cleaned) - window_length) // (num_windows - 1)
        _publish_ecg_monitor("window", index=i, start=i * step_size / fs,
                             end=(i * step_size + window_length) / fs, hf=ln_HRV_HF)


    # # Iterate over the windows to get the HRV_HF
    # # fixed windows size and overlap
    # for i in range(n_windows):
    #     #print(i)
    #     #print(view_ecg_clean[i])
    #     peaks, info = nk.ecg_peaks(view_ecg_clean[i], sampling_rate=fs, correct_artifacts=True, show=False)
    #     hrv_indices = nk.hrv(peaks, sampling_rate=fs, show=False)
    #     ln_HRV_HF = np.log(hrv_indices['HRV_HF'].values[0])
    #     hrv_hf.append(ln_HRV_HF)
    #     #print(hrv_indices['HRV_HF'].values[0])

    #     ### Alternative method to get the HVR_HF, should use the same functions above under the hood ###
    #     # signals, info = nk.ecg_process(view_ecg_clean[i], sampling_rate=fs)
    #     # nk.ecg_plot(signals, info)
    #     # analyze_df = nk.ecg_analyze(signals, sampling_rate=fs)
    #     # print(analyze_df['HRV_HF'])


    # Save the HRV_HF values to a CSV file
    nameCSV = 'HF_Block_' + str(block_ID) + '_' + session_external_ID + '.csv'
    pd.DataFrame(hrv_hf).to_csv(nameCSV, header=False, index=False)

    return hrv_hf
    
def compareShapelets(hf_Data):
    results_shapeletA = []
    results_shapeletB = []

    # Make sure the hf_Data size is the same as the shapelet size
    # What do we do if it is not?
    if len(hf_Data) < shapelet_size:
        return None, None

    hrv_hf = hf_Data[0:shapelet_size]   
    results_shapeletA.append(stats_tools.spearmanr(hrv_hf, shapeletA))
    results_shapeletB.append(stats_tools.spearmanr(hrv_hf, shapeletB))

    # for i in range(0, math.floor(len(hf_Data)/shapelet_size)):
    #     a = i* shapelet_size
    #     b = a + shapelet_size
    #     temp = hf_Data[a:b]
    #     results_shapeletA.append(st.spearmanr(temp, shapeletA))
    #     results_shapeletB.append(st.spearmanr(temp, shapeletB))
    
    shapA_results = pd.DataFrame(results_shapeletA, columns=['rho', 'p value']) 
    shapB_results = pd.DataFrame(results_shapeletB, columns=['rho', 'p value']) 

    return shapA_results,shapB_results

def saveRhoResults(listRho, typeShapelet):
    nameCSV = 'resultsRho_Shapelet_' + typeShapelet + '.csv'
    with open(nameCSV,'a') as f:
        for df in listRho:
            df.to_csv(f)
            f.write("\n")

def saveECG(rawECG, user, block):
    nameCSV = 'ECG_Block_' + str(block) + '_' + user + '.csv'
    pd.DataFrame(rawECG).to_csv(nameCSV, index=False)

def saveRho(rho, typeShapelet, user, block):
    nameCSV = 'Rho_Shapelet_' + typeShapelet + '_Block_' + str(block) + '_' + user + '.csv'
    rho.to_csv(nameCSV,index=False)

def saveRawData(listRaw):
    for i in range(len(listRaw)):
        temp = pd.DataFrame(listRaw[i])
        nameCSV = 'ECG_Data_Block_' + str(i+1) + '.csv'
        temp.to_csv(nameCSV, index=False)
# -*- coding: utf-8 -*-
"""
Last Modified:24/03/2026

Author: Chris Tomsett
"""

#########################################################################
### THIS SCRIPT EXTRACTS INDIVIDUAL FRAMES FROM THE RECORDED IMAGERY  ###
### DESIGNED TO CAPTURE EVERY 1 SECOND, THIS CAN BE ADJUSTED. OUTPUTS ###
### FROM THIS ARE THE IDNIVIDUAL FRAMES AS IMAGES, AS WELL AS GNSS    ###
###       DATA FOR EACH OF THE FRAMES IN A SEPERATE CSV FILE          ###
#########################################################################



####################
###IMPORT MODULES###
####################

import cv2
import math
import os
import re
import pandas as pd
from pymediainfo import MediaInfo
from datetime import datetime, timedelta
import numpy as np
np.set_printoptions(legacy='1.25')


###############################
###USER REQUIRED ADJUSTMENTS###
###############################

# Location of video (if only processing one video)
videoFile = r'' # filepath to video of interest

# Location to store outputted individual images from all or specified video(s)
imagesFolder = r"XXX\BaseStructure\IndividualFrames"

# Identify the number of images per second you would like turned into images
# Leave this as 1 in most scenarios
hz = 1

# Specify the video framerate, this needs to be checked in your original video file
fr = 30

# decode file format of GNSS data (if available)
# this can be either in csv as a logfile, or srt if recorded
GNSS_file = r"XXX\Flight_1.SRT" # ensure the .csv or .srt file extension is included 

# specify the GNSS metadata file
GNSS_Metadata_File = r"XXX\BaseStructure\Pos\GNSS_Data.csv" 




##############################
###GLOBAL PARAMTER SETTINGS###
##############################

# # Get all files in the folder (excluding subfolders)
# files = [os.path.join(videoFolder, f) for f in os.listdir(videoFolder) if os.path.isfile(os.path.join(videoFolder, f))]

# calculate time offset between frames
time_diff = 1/fr
    
### Get start time of video ### 

# Parse the media information
media_info = MediaInfo.parse(videoFile)

# Initialize variable for the start time
video_start_time = None

# Loop through media tracks to find general metadata
for track in media_info.tracks:
    if track.track_type == "General":  # General metadata for the whole video
        if hasattr(track, "tagged_date"):
            video_start_time = track.tagged_date
        elif hasattr(track, "encoded_date"):
            video_start_time = track.encoded_date

# Convert the start time to a Python datetime object, if available
if video_start_time:
    video_start_time = datetime.fromisoformat(video_start_time.replace(" UTC", "")) 
    
    
###################################
### GNSS data reading functions ###
###################################

def SRT_reader(srt_file):
    
    # open file
    with open(srt_file, 'r', encoding='utf-8') as file:
            srt_data = file.read()
    
    # Regular expression pattern to match subtitle blocks
    pattern = r'(\d+)\s+([\d:,]+ --> [\d:,]+)\s+([^\n]+(?:\n[^\n]+)*)'
    
    # Find all matches in the file
    matches = re.findall(pattern, srt_data)
    
    # create an empty variable
    data = [] 
    
    # go through each .srt block
    for each in matches:
        # extract the block of information required
        text = each[2]
        # extract time variable
        time = text.split('\n')[1]
        time = datetime.strptime((time), '%Y-%m-%d %H:%M:%S.%f')
        # extract list of lle data
        lle = text.split('\n')[3].replace('[', '').replace(']', '').split(' ')
        # extract list of gimbal rpy
        rpy = text.split('\n')[6].replace('[', '').replace(']', '').split(' ')
        # extract aircraft yaw
        y = text.split('\n')[5].replace('[', '').replace(']', '').split(' ')[1]
        # specify the values within this to extract
        lat, lon, elev, alti, g_pitch, g_roll, g_yaw, a_yaw = lle[1], lle[3], lle[5], lle[7], rpy[3], rpy[5], rpy[1], y
        # add all this data to the empty variable
        data.append((time, lat, lon, elev, alti, g_pitch, g_roll, g_yaw, a_yaw))
        
    # create a dataframe of the variables and index based on time
    GNSS_DF = pd.DataFrame(data, columns = ['Time', 'Lat', 'Lon', 'Elev', 'Altitude', 'G_Pitch', 'G_Roll', 'G_Yaw', 'A_Yaw'])#.set_index('Time')
    GNSS_DF.iloc[:,1:] = GNSS_DF.iloc[:,1:].apply(pd.to_numeric)
    
    # return df
    return GNSS_DF


def TXT_reader(txt_file):
    
    # read in flight record
    flightrecord = pd.read_csv(txt_file, sep = ',', skiprows = 1)
    
    gnss_data = []
    
    for index, row in flightrecord.iterrows():
        date = row.iloc[0]
        m, d, y, = date.split('/')
        if len(m) < 2:
            m = '0' + m
        if len(d) < 2:
            d = '0' + d
        date = m + '/' + d + '/' + y
        time = row.iloc[1]
        h, m, s = time.split(':')
        if len(h) < 2:
            h = '0' + h
        if len(m) < 2:
            m = '0' + m
        time = h + ':' + m + ':' + s
        
        dt = datetime.strptime((date + ' ' + time), '%m/%d/%Y %I:%M:%S.%f %p')
        
        # # Define the time zones (THIS MAY NOT BE NECCESSARY DEPENDING ON CONTROLLER)
        # shanghai_tz = pytz.timezone('US/Central')
        # uk_tz = pytz.timezone('UTC')
        
        # # Localize the naive datetime to Shanghai timezone
        # aware_shanghai_time = shanghai_tz.localize(dt)
        
        # uk_time = aware_shanghai_time.astimezone(uk_tz)
        
        
        lat = row.iloc[4]
        lon = row.iloc[5]
        elev = row.iloc[6] * 0.3048 #ft to m conversion
        alti = row.iloc[9] * 0.3048 
        g_pitch = row.iloc[56]
        g_roll = row.iloc[57]
        g_yaw = row.iloc[59]
        a_yaw = row.iloc[22]
        
        data = (dt, lat, lon, elev, alti, g_pitch, g_roll, g_yaw, a_yaw)
        
        gnss_data.append(data)
    
    GNSS_DF = pd.DataFrame(gnss_data, columns = ['Time', 'Lat', 'Lon', 'Elev', 'Altitude', 'G_Pitch', 'G_Roll', 'G_Yaw', 'A_Yaw'])#.set_index('Time')
    
    return GNSS_DF

#########################################
###UNDERTAKE INDIVIDUAL IMAGE CREATION###
#########################################

# Check type and run through GNSS data appropriately
if len(GNSS_file) > 0:
    if GNSS_file.endswith('.SRT'):
        GNSS_Data = SRT_reader(GNSS_file)
    elif GNSS_file.endswith('.csv'):
        GNSS_Data = TXT_reader(GNSS_file)
    else:
        print('Check the format of your GNSS data')


GNSS_Metadata = pd.DataFrame(columns = ['Image', 'Lon', 'Lat', 'Elev', 'Altitude', 'Gimal_Yaw', 'Aircraft_Yaw', 'Pitch', 'Roll'])

# # Loop through files to output images
    
# read in video file
cap = cv2.VideoCapture(videoFile)

# obtain frame rate of the video
frameRate = cap.get(5) #frame rate

# update frame rate to match desired rate
frameRate = frameRate/hz

# identify the total number of frames in the video
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# work out time offset of first image
time_start = videoFile.split('_')[-2]
#minutes, seconds = map(int, time_start.split('-'))
minutes = 0
seconds = 0
# work out time of first image
time_first_image =  video_start_time + timedelta(minutes=minutes, seconds=seconds)

while(cap.isOpened()):
    
    # get number of the frame being cycled through
    frameId = cap.get(1) 
    
    # specify if there is a frame, and its number
    ret, frame = cap.read()
    
    # if no frame in image, break the cycle
    if (ret != True):
        break
    
    # if there is nothing left over when dividing the current frame by the desired frame, output an image
    if (frameId % math.floor(frameRate) == 0):
        # define filename and write image
        fileprefix = os.path.basename(videoFile).split('.')[0]
        
        if frameId == 0:
            file_time_extension = str(int(frameId)).zfill(4)
        else:
            file_time_extension = str(int(frameId / 30)).zfill(4)
            
        filename = imagesFolder + "/" + fileprefix + "_image_time_seconds_" +  file_time_extension + ".jpg"
        
        cv2.imwrite(filename, frame)
        
        # Update the image metadata
        # caluclate approx time of image and write to exif data
        time_image = (time_first_image + timedelta(seconds = frameId * time_diff + .0))

        # Export position and orientation to dataframe
        closest_index = (GNSS_Data['Time'] - time_image).abs().idxmin()
        closest_row = GNSS_Data.loc[closest_index]
        pos_info = ((fileprefix + "_image_time_seconds_" +  file_time_extension + ".jpg"), closest_row['Lon'], closest_row['Lat'], closest_row['Elev'], closest_row['Altitude'], 
                    closest_row['G_Yaw'], closest_row['A_Yaw'], closest_row['G_Pitch'], closest_row['G_Roll'])
        GNSS_Metadata.loc[len(GNSS_Metadata)] = pos_info

        print(str(round(frameId / frame_count * 100, 1)) + '% through processing')
        
cap.release()

GNSS_Metadata.to_csv(GNSS_Metadata_File, index = False)

print("Done!")
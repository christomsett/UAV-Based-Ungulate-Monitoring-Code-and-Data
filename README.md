# UAV Based Ungulate Monitoring Code and Data
This repository provides all of the scripts and data to support the an ungulate monitoring paper in review (link tbc).
For thermal video frame extraction, this provides two scripts and a base folder structure for extracting individual thermal video frames and using on-board GNSS data to approximately georeference the images.
For the Bayesian Modelling, there is an R-based analysis script, as well as a zipped folder containing the datasets.

# Folder structure
Within the Video Extractor setup, an empty folder structure is provided which helps to store data within and organise outputs. The location of where each script input should be placed is also linked to this folder structure to help with the running of the scripts. An overview can be seen below:
- Base Structure:
	- Georeferenced_Images:
		- Output location for each of the georeferenced frams of interest
	- Indivudal_Frames:
		- output location for each one-second interval frame from the input thermal videos
	- Pos:
		- Output from the DJI-based positioning files to locate and orientate image frames
	Thermal_Signatures_Log.csv
		- User created csv which takes the time in minutes of each frame and requires converting into seconds of video.
- Video_Frame_Extractor.py
	- The python script for extracting individual frames every second and creating a UAV position file
- Frame_Georeferencer.py
	- The python script for georeferncing each specified frame from the Thermal_Signatures_Log file

Within the Bayesian Analysis setup, there is a completed R environment script for undertaking the modelling, as well as a zipped dataset.

# Workflow for thermal video extraction
1. Copy the BaseStructure to a location of your choosing.
2. Within your video, identify the time of the frames to be georeferenced and add them to the Thermal_Signatures_Log.csv
3. Convert the minutes and seconds values to seconds. this can usually be achived by multiplying the minutes:seconds cell by 86400. See here for more information: https://www.w3schools.com/excel/excel_howto_convert_time_to_seconds.php
4. Open the Video_Frame_Extractor.py file, edit the user defined inputs, and run the script.
5. Open the Frame_Georeferencer.py file, edit the user defined inputs again, and run the script. 
6. Load outputs into GIS or other mapping sofwtare to view outputs.
# -*- coding: utf-8 -*-
"""
Last Modified:24/03/2026

Author: Chris Tomsett
"""

import os
import pandas as pd

import pyproj
from osgeo import gdal, osr
from affine import Affine

import re
from datetime import datetime



##################################################################################
###  THIS SCRIPT TAKES THE OUTPUTS FROM THE VIDEO FRAMES ETXRACTOR SCRIPT AND  ###
###   USES THIS TO CREATE GEOREFERENCED FOOTPRINTS OF EACH IMAGES BASED ON A   ###
### TERRAIN MODEL SPECIFIED BY THE USER. AS SUCH THIS PROVIDES A GOOD ESTIMATE ###
###   OF GROUND COVERAGE FROM THE EXTRACTED IMAGERY AS OPPOSSED TO A FULLY     ###
### GEOREFERENCED IMAGE FROM THE VIDEO FEED. THE POSITION OF THE UAV IS REAL-  ###
###    TIME NOT POST-PROCESSED, AND USES THE UAVS INTERNAL ORIENTATION.        ###
##################################################################################

####
#### Camera parameters, these need to be adjusted for your camera settings
#### Current settings based off a DJI Zenmuse H20N setup on a DJI M300
####

focal_length = 12.0  # mm (https://enterprise.dji.com/zenmuse-h20n/specs) 
sensor_size = (7.680, 6.144)  # mm (width, height) (https://forum.dji.com/thread-236402-1-1.html)
image_size = (640, 512)  # pixels (width, height) (https://enterprise.dji.com/zenmuse-h20n/specs) 



####
#### User defined parameters
####

# location of photos at every second in video, the output of the previous script
individual_frames_fp = r"XXX\BaseStructure\Individual_Frames"

# csv with times of thermal sightings in full frame, this is a user produced csv provided in the GitHub documentation
thermal_signatures_log_fp = r"XXX\BaseStructure\Thermal_Signatures_Log.csv"
thermal_signatures_log = pd.read_csv(thermal_signatures_log_fp)

# csv of the location and orientation data for each exported frame, the output of previous script
photo_loc_fp = r"XXX\BaseStructure\Pos\GNSS_Data.csv"
photo_loc = pd.read_csv(photo_loc_fp)

# flight log for determining aircraft to dem offset for height above ground calculations, the same flight log input as the prior script, can be .csv logfile or .srt
dji_flight_log_fp = r"XXX\Flight_1.SRT"

# output folder for 'georeferenced' thermal imagery, the georefercned folder in folder structure
out_folder = r"XXX\BaseStructure\Georeferenced_Images"

# output name to idenitfy merged tiles, e.g. a video namae/study site/location/transect
out_prefix = ""

# 5m res dem to be used for reference, a suitable global or local dem can be used in a matching cooridnate system to the above
dem_fp = r"XXX\XXX.tif"



####
#### Functions used throughout the script
####

def get_footprint_size_m(sensor_width, focal_length, image_width, image_height, altitude):
    gsd = (sensor_width * altitude * 100) / (focal_length * image_width)
    
    footprint_width  = (gsd * image_width) / 100
    footprint_height  = (gsd * image_height) / 100
    
    return (footprint_width, footprint_height, gsd)

def lat_lon_2_east_north(latitude, longitude):
    # Convert camera center to UTM Zone 30N
    wgs84 = pyproj.Proj(proj="latlong", datum="WGS84")
    utm_proj = pyproj.Proj(proj="utm", zone=30, datum="WGS84")
    easting, northing = pyproj.transform(wgs84, utm_proj, longitude, latitude)
    
    return (easting, northing)

def get_image_bbox(east_north, footprint_size):
    easting, northing = east_north
    width, height , gsd = footprint_size
    
    half_width = width / 2
    half_height = height / 2
    
    west = easting - half_width
    south = northing - half_height
    east = easting + half_width
    north = northing + half_height
    
    return (west, south, east, north)

def write_jpeg_worldfile(jpeg_path, geo_transform):    
    """
    Write a JPEG worldfile (.jgw) from the geo_transform.
    
    :param jpeg_path: Path to the JPEG image file
    :param geo_transform: GDAL GeoTransform tuple
        (top_left_x, pixel_width, rotation_x, top_left_y, rotation_y, pixel_height)
    """
    # Extract GeoTransform values
    top_left_x, pixel_width, rotation_x, top_left_y, rotation_y, pixel_height = geo_transform
    
    # Write world file (.jgw)
    worldfile_path = jpeg_path.replace('.jpg', '.jgw')
    
    with open(worldfile_path, 'w') as f:
        f.write(f"{pixel_width}\n")    # Pixel size in the X direction (meters/pixel)
        f.write(f"{rotation_x}\n")     # Rotation in the X axis (usually 0)
        f.write(f"{rotation_y}\n")     # Rotation in the Y axis (usually 0)
        f.write(f"{pixel_height}\n")   # Pixel size in the Y direction (negative)
        f.write(f"{top_left_x}\n")     # X coordinate of the center of the upper left pixel
        f.write(f"{top_left_y}\n")     # Y coordinate of the center of the upper left pixel
    
    print("World file written")

def raster_center_pixel(raster):
    width, height = raster.RasterXSize, raster.RasterYSize
    
    xmed = width / 2
    ymed = height / 2

    return (xmed, ymed)

def rotate_raster(affine_matrix, angle, pivot = None):
    # get GDAL specific affine format
    affine_src = Affine.from_gdal(*affine_matrix)
    
    #apply a rotation
    affine_dst = affine_src * affine_src.rotation(angle, pivot)
    
    
    #return the rotated matrix in gdal format
    return affine_dst.to_gdal()

def dem_offset(coords, start_altitude, dem_fp):
    # get eastings and northings
    easting = coords[0]
    northing = coords[1]
    
    # load in dem
    dem = gdal.Open(dem_fp)
    
    # get geo info of dem
    transform = dem.GetGeoTransform()
    band = dem.GetRasterBand(1) # assume single band dem
    
    # get pixel coords from utm coords
    pixel_x = int((easting - transform[0]) / transform[1])
    pixel_y = int((northing - transform[3]) / transform[5])
    
    # read elevation output
    elevation = band.ReadAsArray(pixel_x, pixel_y, 1, 1)[0][0]
    
    # calculate offset
    elev_offset = start_altitude - elevation    
    
    # close dem file
    dem = None
    
    return(elev_offset)

def image_elevation_calculator(camera_location, altitude, dem_fp, offset):
    # get posiiton variables
    easting = camera_location[0]
    northing = camera_location[1]
    
    # load in dem
    dem = gdal.Open(dem_fp)
    
    # get geo info of dem
    transform = dem.GetGeoTransform()
    band = dem.GetRasterBand(1) # assume single band dem
    
    # get pixel coords from utm coords
    pixel_x = int((easting - transform[0]) / transform[1])
    pixel_y = int((northing - transform[3]) / transform[5])
    
    # read elevation output
    dem_elevation = band.ReadAsArray(pixel_x, pixel_y, 1, 1)[0][0]
    
    # identify height of UAV above ground
    height = (altitude) - offset - dem_elevation
    
    # close dem dataset
    dem = None
    
    # return height value
    return(height)
    

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
if len(dji_flight_log_fp) > 0:
    if dji_flight_log_fp.endswith('.SRT'):
        dji_flight_log = SRT_reader(dji_flight_log_fp)
    elif dji_flight_log_fp.endswith('.csv'):
        dji_flight_log = TXT_reader(dji_flight_log_fp)
    else:
        print('Check the format of your GNSS data')


####
#### Calcultae offset between aircraft altitude and dem when on the ground
####

# get eastings and northings and elevation from dji flight log of first position
dji_strt_lat = dji_flight_log.iloc[0, 1]
dji_strt_lon = dji_flight_log.iloc[0, 2]
dji_strt_alti = dji_flight_log.iloc[0, 4] * 0.3048

# convert lat long to eastings and northings in UTM30N
start_coords = lat_lon_2_east_north(dji_strt_lat, dji_strt_lon)

# calculate offset between height on ground of uav and height of dem
# this can be used to adjust flight altitude to get height over ground
dem_offset = dem_offset(start_coords, dji_strt_alti, dem_fp)
dem_offset = 0



####
#### Cycle through each identified thermal timestamp to produce georeferenced outputs
####

# identify a list of times
times = list(thermal_signatures_log.iloc[:, 1])

# cycle through each time step of interest
for time in times:
    
    # get zero padded version of time to match file naming convention
    time = str(int(time)).zfill(4)
    
    # match to photo ending in that timecode
    for f in os.listdir(individual_frames_fp):
        if f.split('.')[0].endswith(time):
            if len(f.split('.')) < 3:
                if f.split('.')[1] == 'jpg':
                    frame = f
    
    # find matching camera position information
    image_loc_data = photo_loc[photo_loc['Image'] == frame]
    
    # convert the position to eastings and northings, and re-add elev data
    image_pos_utm = lat_lon_2_east_north(image_loc_data['Lat'].iloc[0], 
                                         image_loc_data['Lon'].iloc[0])
    
    # identify height above dtm
    image_height = image_elevation_calculator(image_pos_utm, 
                                              image_loc_data['Altitude'].iloc[0], 
                                              dem_fp, dem_offset)
    
    # identify image footprint from this information
    image_footprint = get_footprint_size_m(sensor_size[0], focal_length, 
                                           image_size[0], image_size[1], 
                                           image_height)
    
    # obtain image bbox from above footprint
    image_bbox = get_image_bbox(image_pos_utm, image_footprint)
    
    # create a jpeg worldfile in the original directory to georefernce imagery based on the above
    geo_transform = [image_bbox[0], image_footprint[2] / 100, 0.0, image_bbox[3], 0.0, -image_footprint[2] / 100]  # Example GeoTransform for UTM 30N
    jpeg_path = os.path.join(individual_frames_fp, frame)
    write_jpeg_worldfile(jpeg_path, geo_transform)
    
    
    #### ROTATE THE CREATED GEOREFERENCED DATASET
    
    # identify the most consistent offset between aircraft and gimbal yaw
    # seems to be a recurring issue which doesn't orientate aircraft correctly
    gimbal_offset = (photo_loc['Aircraft_Yaw'] - photo_loc['Gimal_Yaw']).mode()[0]
    
    # get rotation value from gps log
    aircraft_heading = image_loc_data['Gimal_Yaw'].iloc[0] + gimbal_offset
    
    ### create a copy of the dataset as a tif
    # open jpeg dataset
    gdal_dataset_jpg = gdal.Open(jpeg_path)
    # create output tif file name
    output_tif = os.path.join(out_folder, frame.replace('.jpg', '.tif'))
    # create the copy as a tif
    gdal.Translate(output_tif, gdal_dataset_jpg)
    # open this tif file to work on
    gdal_dataset_tif = gdal.Open(output_tif)

    ### rotate tif image
    # get affine details of first dataset
    gt_affine = gdal_dataset_tif.GetGeoTransform()
    # get raster centre
    center = raster_center_pixel(gdal_dataset_tif)
    # rotate matrix
    gdal_dataset_tif.SetGeoTransform(rotate_raster(gt_affine, aircraft_heading, center))

    ### set CRS of output tif
    # extract information of utm30n crs (epsg no. 32630)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32630)
    # apply crs to tif file
    gdal_dataset_tif.SetProjection(srs.ExportToWkt())

    # flush cache to apply changes and remove datasets to close them
    gdal_dataset_tif.FlushCache()
    gdal_dataset_jpg = None
    gdal_dataset_tif = None
    
    
    
####
#### Merge all created rasters into one continous raster
####

# list all the above created georeferenced images
georeffed_rasters = []
for i in os.listdir(out_folder):
    if i.endswith('.tif'):
        georeffed_rasters.append(os.path.join(out_folder, i))

# merge them together using gdal warp and the list        
merged = gdal.Warp(os.path.join(out_folder, out_prefix + '_Merged_Thermal_Images.tif'),
                   georeffed_rasters, format = 'GTiff', options = ["COMPRESS=LZW", "TILED=YES"])

# close the merged raster dataset
merged = None

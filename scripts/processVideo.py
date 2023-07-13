# install packages
import numpy as np
import sys
import io
import os
import glob
import re
import os
import exiftool
import datetime as dt
import pandas as pd
import os
import pickle
import shutil
from moviepy.editor import *
import moviepy
from pathlib import Path

# local packages
# https://github.com/rpuntaie/syncstart
from syncstart import file_offset

# set directories
data_dir = '../data'
raw_dir = '../data/raw/'
processed_dir = '../data/processed/'
compressed_dir = '../data/compressed'
final_dir = '../data/final'

# make directories if they dont exist
dirs = [
  data_dir,
  raw_dir, 
  processed_dir, 
  compressed_dir,
  final_dir, 
]
for d in dirs:
  if not os.path.exists(d):
    os.makedirs(d, exists_)

# given a filename for a video, returns the start/end times, pulled from metadata
# used to check if two video files overlap
def getTimes(filename):

  with exiftool.ExifToolHelper() as et:

    # get metadata
    metadata = et.get_metadata(filename)
    metadata = metadata[0]

    # get endtime frome metadata
    endTime = metadata['QuickTime:CreateDate'] # 2023:03:22 02:09:16
    endTime = pd.to_datetime(endTime, format='%Y:%m:%d %H:%M:%S', utc=True).tz_convert('Australia/Perth')

    # calculated start time from endtime and duration
    duration = metadata['QuickTime:Duration']
    startTime = endTime - dt.timedelta(seconds=duration)

  return startTime, endTime

# list of filenames in raw directory to process
filenames = [f for f in os.listdir(raw_dir) if f.endswith("mp4")]
filenames.sort()

# start looping through filenames (will remove processed filenames making list shorter)
while len(filenames) > 0:
  
  # start with first filename as filenameA
  fnameA = filenames[0]
  print('fnameA ', fnameA)

  # pull start, end times
  stimeA, etimeA = getTimes(raw_dir + fnameA)
  print(stimeA, stimeA)

  # create list to interate through not including fnameA, will check if theres intersection
  fs = [f for f in filenames if f != fnameA]

  # start off assuming theres no other file that interects
  matching_filenames = False

  # iterate through list
  for fnameB in fs:

    print('fnameB ', fnameB)

    # get start and end times of fnameB
    stimeB, etimeB = getTimes(raw_dir + fnameB)

    # if theres no overlap, exit out of loop
    if not ((stimeA <= etimeB) and (etimeA >= stimeB)):
      continue 

    # # trim videos
    # trimVideos(raw_dir=raw_dir, fnameA=fnameA, fnameB=fnameB)

    # get min start time from either file, create filename for new video
    stimeA, etimeA = getTimes(raw_dir + fnameA)
    stimeB, etimeB = getTimes(raw_dir + fnameB)
    stime = min([stimeA, stimeB])
    fname = '{stime}_processed.mp4'.format(stime=stime.strftime('%Y-%m-%d %H.%M.%S'))
    fname_small = '{stime}_processed.mp4_small'.format(stime=stime.strftime('%Y-%m-%d %H.%M.%S'))

    # if there is overlap, use the audio form both files to claculate delay
    (fname, offset) = file_offset(in1=raw_dir + fnameA, in2=raw_dir + fnameB,
      take=max([(etimeB - stimeB).total_seconds(), (etimeA - stimeA).total_seconds()]), 
      # show=True
      show=False
      )
    if fname == raw_dir + fnameA:
      delayA = offset
      delayB = 0
    else:
      delayA = 0
      delayB = offset
    
    # bring in clips from video files 
    clipA = VideoFileClip(raw_dir + fnameA)
    clipB = VideoFileClip(raw_dir + fnameB)

    # calculate min duration, used to trim videos to the same length
    duration = min([clipA.duration - delayA, clipB.duration - delayB])

    clipA = clipA.subclip(delayA, duration + delayA)
    clipB = clipB.subclip(delayB, duration + delayB)

    # if width and height are wrong way round, flip
    if clipA.w > clipA.h:
      w = clipA.w
      h = clipA.h
      clipA = clipA.resize((h, w))

    if clipB.w > clipB.h:
      w = clipB.w
      h = clipB.h
      clipB = clipB.resize((h, w))

    # get min start time from either file, create filename for new video
    stime = min([stimeA, stimeB])
    fname = '{stime}_processed.mp4'.format(stime=stime.strftime('%Y-%m-%d %H.%M.%S'))
    fname_small = '{stime}_processed.mp4_small'.format(stime=stime.strftime('%Y-%m-%d %H.%M.%S'))

    # get max width/height from videos
    width = max([clipA.w, clipB.w])
    height = max([clipA.h, clipB.h])

    # resize each clip so they're the same
    clipA = clipA.resize((width, height))
    clipB = clipB.resize((width, height))
    
    # create new clip that is the videos next to each other, and save to processed directory
    final = clips_array([[clipA, clipB]])
    final = final.resize((2*width, height))
    if fname not in os.listdir(processed_dir):
      print('Writing concat file :',  processed_dir + fname)
      final.write_videofile(processed_dir + fname,
        codec='libx264',
        threads=4,
        # crf=20,
        fps=24,
        audio=False,
        preset='ultrafast', 
        # progress_bar=False,
        logger=None,
    )

    # # create a small version of this video, to save space
    # final = final.resize(0.1)
    # if fname_small not in os.listdir(processed_dir):
    #   final.write_videofile(processed_dir + fname_small,
    #     codec='libx264',
    #     threads=4,
    #     fps=24,
    #     audio=False,
    #     preset='ultrafast', 
    #     # progress_bar=False,
    #     logger=None,
    #     )

    # if we've made it this far we have found a matching filename (fnameB) for fnameA, 
    # we don't want to reprocess fnameB, so remove from list
    matching_filenames = True
    if fnameB in filenames:
      filenames.remove(fnameB)

  # if we've gone through entire list and no fnameB overlaps with fnameA, just save fnameA in processed dir
  if matching_filenames == False:
    print('no matching files for : ', fnameA)
    print('Writing single file :',  processed_dir + fnameA)
    fname = stimeA.strftime('%Y-%m-%d %H.%M.%S') + '_' + fnameA
    if fname not in os.listdir(processed_dir):
      os.system('''ffmpeg -i "{input}" -c copy -an "{output}"
        '''.format(
          input=raw_dir + fnameA,
          output=processed_dir + fname,
          )
        )

  # remove fnameA from filenames and start again
  if fnameA in filenames:
    filenames.remove(fnameA)

  print('')

# compress processed videos
for fname in os.listdir('../data/processed/'):
  print(fname)
  if fname not in os.listdir('../data/compressed/'):
    os.system('ffmpeg -i "../data/processed/{input}" -vcodec libx265 -crf 24 "../data/compressed/{output}"'.format(input=fname, output=fname))




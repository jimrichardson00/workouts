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
from syncstart import file_offset

# set directories
raw_dir = '../data/raw/'
processed_dir = '../data/processed/'

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

def trimVideos(raw_dir, fnameA, fnameB):

  # pull start, end times
  stimeA, etimeA = getTimes(raw_dir + fnameA)

  # get start and end times of fnameB
  stimeB, etimeB = getTimes(raw_dir + fnameB)

  # trim the larger of fnameA, fnameB
  stime = max([stimeA, stimeB]) - dt.timedelta(seconds=5)
  etime = min([etimeA, etimeB]) + dt.timedelta(seconds=5)

  # fname a
  t1A = max([(stime - stimeA).total_seconds(), 0])
  t2A = min([(etime - stimeA).total_seconds(), (etimeA - stimeA).total_seconds()])
  os.rename(raw_dir + fnameA, raw_dir + 'unclipped_' + fnameA)
  moviepy.video.io.ffmpeg_tools.ffmpeg_extract_subclip(
    filename=raw_dir + 'unclipped_' + fnameA,
    t1=t1A, t2=t2A,
    targetname=raw_dir + 'clipped_' + fnameA
  )
  os.system('''ffmpeg -i {inf} -i {out} -map 1 -map_metadata 0 -c copy {fixed}'''.format(
      inf=raw_dir + 'unclipped_' + fnameA, 
      out=raw_dir + 'clipped_' + fnameA, 
      fixed=raw_dir + fnameA, 
    )
  )

  # fname b
  t1B = max([(stime - stimeB).total_seconds(), 0])
  t2B = max([(etime - stimeB).total_seconds(), (etimeB - stimeB).total_seconds()])
  os.rename(raw_dir + fnameB, raw_dir + 'unclipped_' + fnameB)
  moviepy.video.io.ffmpeg_tools.ffmpeg_extract_subclip(
    filename=raw_dir + 'unclipped_' + fnameB,
    t1=t1B, t2=t2B,
    targetname=raw_dir + 'clipped_' + fnameB
  )
  os.system('''ffmpeg -i {inf} -i {out} -map 1 -map_metadata 0 -c copy {fixed}'''.format(
      inf=raw_dir + 'unclipped_' + fnameB, 
      out=raw_dir + 'clipped_' + fnameB, 
      fixed=raw_dir + fnameB, 
    )
  )

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

    # use the calculated delay to make sure videos start at the same time

    # using ffmpeg

    # # extract 
    # moviepy.video.io.ffmpeg_tools.ffmpeg_extract_subclip(filename=raw_dir + fnameA, t1=delayA, t2=duration + delayA, targetname='left.mp4')
    # moviepy.video.io.ffmpeg_tools.ffmpeg_extract_subclip(filename=raw_dir + fnameB, t1=delayB, t2=duration + delayB, targetname='right.mp4')

    # # create new clip that is the videos next to each other, and save to processed directory
    # print('Writing concat file :',  processed_dir + fname)
    # if fname not in os.listdir(processed_dir):
    #   os.system('''ffmpeg -i left.mp4 -i right.mp4 -filter_complex hstack "{output}"
    #     '''.format(output=processed_dir + fname)
    #     )

    # using moviepy

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
    # final = final.subclip(0, 5)
    if fname not in os.listdir(processed_dir):
      print('Writing concat file :',  processed_dir + fname)
      final.write_videofile(processed_dir + fname,
        codec='libx265',
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

    # # put everything back the way it was
    # final.close()
    # clipB.close()
    # os.remove(Path(Path(raw_dir), fnameB))
    # os.replace(Path(Path(raw_dir), 'unclipped_' + fnameB), Path(Path(raw_dir), fnameB))

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
      # shutil.copy(raw_dir + fnameA, processed_dir + fname)

  # clipA.close()
  # os.replace(Path(Path(raw_dir), 'unclipped_' + fnameA), Path(Path(raw_dir), fnameA))

  # remove fnameA from filenames and start again
  if fnameA in filenames:
    filenames.remove(fnameA)

  print('')

# compress processed videos
for fname in os.listdir('../data/processed/'):
  print(fname)
  if fname not in os.listdir('../data/compressed/'):
    os.system('ffmpeg -i "../data/processed/{input}" -vcodec libx265 -crf 24 "../data/compressed/{output}"'.format(input=fname, output=fname))




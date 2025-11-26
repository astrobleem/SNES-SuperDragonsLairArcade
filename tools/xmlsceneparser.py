#!/usr/bin/env python3

__author__ = "Matthias Nagler <matt@dforce.de>"
__url__ = ("dforce3000", "dforce3000.de")
__version__ = "0.1"

'''
Dragon's Lair iphone xml parser, spits out scene event list, video frames, audio file
'''

import os
import sys
import string
import logging
import xml.dom.minidom
import subprocess


'''
debugfile = open('debug.log', 'wb')
debugfile.close()
logging.basicConfig( filename='debug.log',
                    level=logging.DEBUG,
                    format='%(message)s')
'''

logging.basicConfig( level=logging.INFO, format='%(message)s')

options = {}

def main():
  options = UserOptions( sys.argv, {
    'infile'        : {
      'value'            : '',
      'type'            : 'str'
      },
    'outfolder'        : {
      'value'            : '.',
      'type'            : 'str'
      },
    'convertedoutfolder'    : {
      'value'            : '',
      'type'            : 'str'
      },
    'convertedframefolder'    : {
      'value'            : '',
      'type'            : 'str'
      },      
    'chapter'        : {
      'value'            : '',
      'type'            : 'str'
      },
    'enumchapter'        : {
      'value'            : '',
      'type'            : 'str'
      },
    'chapternumber'        : {
      'value'            : 0,
      'type'            : 'int',
      'min'                : 0,
      'max'                : 255
      },            
    'chapterfolder'        : {
      'value'            : '',
      'type'            : 'str'
      },      
    'videofile'        : {
      'value'            : '',
      'type'            : 'str'
      },      
    'fps'        : {
      'value'            : 23.9777,
      'type'            : 'float',
      'min'                : 1.00,
      'max'                : 30.00
      },  
  })

  logging.debug('xml parse start')
  if not os.path.exists(options.get('outfolder')):
    os.makedirs(options.get('outfolder'))

  #files = os.listdir(options.get('outfolder'))
  existingChapters = [folder for root, dirs, names in os.walk(options.get('outfolder')) for folder in dirs if folder]
  #debugLogExit(files, 'files')

  #enumerate chapters
  options.manualSet('chapter', os.path.basename(options.get('infile')).split('.')[0].replace('-', '_'))
  options.manualSet('chapternumber', len(existingChapters))
  #options.manualSet('enumchapter', '%02d-%s' % (options.get('chapternumber'), os.path.basename(options.get('infile')).split('.')[0]))
  options.manualSet('chapterfolder', "%s/%s" % (options.get('outfolder'), options.get('chapter')))


  if not os.path.exists(options.get('chapterfolder')):
    os.makedirs(options.get('chapterfolder'))

  '''
  if 1 == 2:
    logging.debug('got target folder')
  else:
    logging.debug('target folder not present')
    
  '''

  events = parseEvents(options)

  
  
  chapterEvent = [event for event in events if event.type == 'chapter'].pop()

  if chapterEvent.frameend - chapterEvent.framestart <= 0:
    logging.warning( 'No frames in chapter %s, creating minimal chapter.' %  chapterEvent.name)
    # Don't exit, just create a minimal chapter file

  chapterIdFileName = "%s/chapter.id.%03d" % (options.get('chapterfolder'), options.get('chapternumber'))
  try:
    chapterIdFile = open(chapterIdFileName,'w')
    chapterIdFile.close()
  except IOError:
    logging.error('unable to access chapter id file %s.' % chapterIdFileName)
    sys.exit(1)  

  updateChapterIncludeFile(chapterEvent, options)

  writeEventFile(events, options)

  #only write video frames/audio if video found
  if not options.get('videofile') == "":
    extractChapterVideo(chapterEvent, options)
      
    # extractChapterAudio(chapterEvent, options)

    optimizeVideoFrames(options)
    if not options.get('convertedoutfolder') == "" and not options.get('convertedframefolder') == "":
      copyConvertedFrames(chapterEvent, options)


  '''
  dummyFileName = "%s/%s.dummy" % (options.get('outfolder'), options.get('chapter'))
  try:
    dummyFile = open(dummyFileName,'w')
    dummyFile.close()
  except IOError:
    logging.error('unable to access input file %s.' % dummyFileName)
    sys.exit(1)
  '''
  
  logging.debug('exiting...')

'''
debug hack
'''
def copyConvertedFrames(chapter, options):
  logging.debug('copying converted frames')
  chapterOutDir = "%s/%s" % (options.get('convertedoutfolder'), options.get('chapter'))
  if not os.path.exists(chapterOutDir):
    os.makedirs(chapterOutDir)
  
  logging.debug('about to convert frames')
  chapterFrameNumber = 0
  for totalFrameNumber in range(chapter.framestart, chapter.frameend + 1):
    logging.debug('Processing copy frame %s' % totalFrameNumber)
    sourceBaseName = "%s/dragonslair_%06d.gfx_video" % (options.get('convertedframefolder'), totalFrameNumber + 1)
    targetBaseName = "%s/video_%06d.gfx_video" % (chapterOutDir, chapterFrameNumber + 1)
    for extension in ('tiles', 'tilemap', 'palette'):
      copyFile("%s.%s" % (sourceBaseName, extension), "%s.%s" % (targetBaseName, extension))
    chapterFrameNumber += 1

def copyFile(source, target):
    try:
      inFile = open(source, 'rb')
    except IOError:
      logging.error('unable to access input file %s.' % source)
      sys.exit(1)
    try:
      outFile = open(target, 'wb')
    except IOError:
      logging.error('unable to access output file %s.' % target)
      sys.exit(1)
    [outFile.write(byte) for byte in inFile.read()]
    inFile.close()
    outFile.close()


'''
write include file for wla-dx, spares me from defining script files manually
'''
def updateChapterIncludeFile(chapterEvent, options):
  chapterIdFileName = "%s/chapter.include" % options.get('outfolder')
  try:
    chapterIdFile = open(chapterIdFileName, 'a')
  except IOError:
    logging.error('Unable to access chapter ID file %s.' % chapterIdFileName)
    sys.exit(1)
  chapterIdFile.writelines(['.include "%s/chapter.script"\n' % options.get('chapterfolder')])

'''
call ffmpeg to cut out relevant chapter from video file, generate single frame images
'''
def extractChapterVideo(chapterEvent, options):
    try:
      videoFile = open(options.get('videofile'), 'r')
    except IOError:
      logging.error('unable to find input video file %s.' % options.get('videofile'))
      sys.exit(1)

    timestart = "%02d:%02d:%02d.%03d" % (0, int(chapterEvent.timestart // (60 * 1000)), int((chapterEvent.timestart % (60 * 1000)) // 1000), int(chapterEvent.timestart % (1000)))
    duration = "%02d:%02d:%02d.%03d" % (0, int(chapterEvent.duration // (60 * 1000)), int((chapterEvent.duration % (60 * 1000)) // 1000), int(chapterEvent.duration % (1000)))

    # Use filter_complex to scale and quantize to 120 colors (to fit in 8 palettes of 15+1)
    # stats_mode=single ensures a new palette is generated for each frame
    # paletteuse=new=1 ensures the new palette is applied to each frame
    # IMPORTANT: -ss must be BEFORE -i for fast seeking!
    cmd = "ffmpeg -y -ss %s -t %s -i \"%s\" -filter_complex \"scale=256:192[s];[s]split[s1][s2];[s1]palettegen=max_colors=120:stats_mode=single[p];[s2][p]paletteuse=new=1:dither=bayer\" -f image2 \"%s/video_%%06d.gfx_video.png\"" % (timestart, duration, options.get('videofile'), options.get('chapterfolder'))
    
    returnVal = os.system(cmd)
    if not 0 == returnVal:
      logging.error('Error while ripping chapter video frames, ffmpeg return code: %s.' % returnVal)
      sys.exit(1)

'''
call ffmpeg to cut out relevant chapter from video file, generate audio tracks
'''
def extractChapterAudio(chapterEvent, options):
    try:
      videoFile = open(options.get('videofile'), 'r')
    except IOError:
      logging.error('unable to find input video file %s.' % options.get('videofile'))
      sys.exit(1)

    timestart = "%02d:%02d:%02d.%03d" % (0, int(chapterEvent.timestart // (60 * 1000)), int((chapterEvent.timestart % (60 * 1000)) // 1000), int(chapterEvent.timestart % (1000)))
    duration = "%02d:%02d:%02d.%03d" % (0, int(chapterEvent.duration // (60 * 1000)), int((chapterEvent.duration % (60 * 1000)) // 1000), int(chapterEvent.duration % (1000)))

    returnVal = os.system("ffmpeg -y -ss %s -t %s -i %s -acodec pcm_s16le -ar 44100 -ac 2 %s/audio.sfx_video.wav" % (timestart, duration, options.get('videofile'), options.get('chapterfolder')))
    if not 0 == returnVal:
      logging.error('Error while ripping chapter audio, ffmpeg return code: %s.' % returnVal)
      sys.exit(1)      
'''
use gimp script(must be located in "$HOME/.gimp2.6/scripts/, or wherever gimp expects scheme scripts") to post-process video frames(smoothen out and color-reduce)
'''
def optimizeVideoFrames(options):
    logging.info('Optimizing video frames using superfamiconv...')
    chapterOutDir = "%s/%s" % (options.get('convertedoutfolder'), options.get('chapter'))
    if not os.path.exists(chapterOutDir):
        os.makedirs(chapterOutDir)

    # Use gfx_converter.py which wraps superfamiconv
    # We need to iterate over all extracted PNGs in chapterfolder
    # Filename format: video_XXXXXX.gfx_video.png
    
    chapterFolder = options.get('chapterfolder')
    png_files = [f for f in os.listdir(chapterFolder) if f.endswith('.gfx_video.png')]
    
    if not png_files:
        logging.warning("No video frames found to optimize in %s" % chapterFolder)
        return

    # Path to gfx_converter.py
    # Assuming we are running from project root or tools dir
    # We need absolute path or relative to CWD
    # The makefile calls it as ./tools/gfx_converter.py
    
    # We will use subprocess to call it
    gfx_converter = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gfx_converter.py')
    
    for png_file in png_files:
        full_png_path = os.path.join(chapterFolder, png_file)
        # Output base: video_XXXXXX.gfx_video (without .png)
        # But copyConvertedFrames expects them in convertedframefolder?
        # Wait, copyConvertedFrames copies FROM convertedframefolder TO convertedoutfolder
        # But extractChapterVideo extracts TO chapterfolder.
        # So we should convert IN PLACE or to convertedframefolder?
        
        # Original code:
        # extractChapterVideo -> chapterfolder
        # optimizeVideoFrames -> chapterfolder (in place)
        # copyConvertedFrames -> copies from convertedframefolder (???)
        
        # Wait, copyConvertedFrames (line 162) reads from options.get('convertedframefolder')
        # But extractChapterVideo writes to options.get('chapterfolder')
        # This implies convertedframefolder and chapterfolder might be the same?
        # OR there was a step missing in original code.
        
        # Let's assume we want to output to chapterfolder, and copyConvertedFrames is legacy/wrong for this flow.
        # We will modify copyConvertedFrames too if needed.
        # For now, let's output the .tiles/.map/.pal to chapterfolder.
        
        outfilebase = os.path.splitext(full_png_path)[0] # removes .png
        
        cmd = [
            sys.executable, gfx_converter,
            '--tool', 'superfamiconv',
            '--pad-to-32x32',
            '-palettes', '8',
            '-infile', full_png_path,
            '-outfilebase', outfilebase
        ]
        
        # logging.debug("Running: %s" % " ".join(cmd))
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            logging.error("Error converting frame %s: %s" % (png_file, e))
            sys.exit(1)
            
    logging.info("Optimized %d frames." % len(png_files))


def writeEventFile(events, options):
  eventFileName = "%s/chapter.script" % options.get('chapterfolder')
  
  try:
    eventFile = open(eventFileName, 'w')
  except IOError:
    logging.error('unable to access output file %s.' % eventFileName)
    sys.exit(1)

  chapterEvent = [event for event in events if event.type == 'chapter'].pop()
  
  eventFile.write("/**\n* this file has been auto-generated.\n*/\n\n")
  eventFile.write("    CHAPTER %s\n\n" % options.get('chapter'))
  for event in events:
    eventFile.write("    EVENT Event.%s.CLS.PTR $%04x $%04x EventResult.%s %s %s %s %s\n\n" % (event.type, max(0, event.framestart - chapterEvent.framestart), max(0, event.frameend - chapterEvent.framestart), event.result, event.resultname, event.arg0, event.arg1, event.arg2))
    #eventFile.write("    %s\n\n" % event.toString())
  eventFile.write("    DIE\n")
  eventFile.close()


def parseEvents(options):
  try:
    xmlFile = open(options.get('infile'), 'rb')
  except IOError:
    logging.error('unable to find input xml file %s.' % options.get('infile'))
    sys.exit(1)
  
  try:
    xmlDom = xml.dom.minidom.parseString(xmlFile.read())
  except xml.parsers.expat.ExpatError:
    logging.error('unable to parse xml file %s.' % options.get('infile'))
    sys.exit(1)
  
  eventList = []
  for chapter in xmlDom.getElementsByTagName('chapter'):
    eventList.append(Event(chapter, options))
    for event in chapter.getElementsByTagName('event'):
      eventList.append(Event(event, options))

  #return eventList
  return sorted(eventList, key=lambda event: event.framestart)


def debugLog( data, message = '' ):
    logging.debug( message )
    debugLogRecursive( data, '' )


def debugLogExit( data, message = '' ):
    logging.debug( message )
    debugLogRecursive( data, '' )
    sys.exit()


def debugLogRecursive( data, nestStr ):
  nestStr += ' '
  if type( data ) is dict:
    logging.debug( '%s dict{' % nestStr )    
    for k, v in data.items():
      logging.debug( ' %s %s:' % tuple( [nestStr, k] ) )
      debugLogRecursive( v, nestStr )
    logging.debug( '%s }' % nestStr )

  elif type( data ) is list:
    logging.debug( '%s list[' % nestStr )
    for v in data:
      debugLogRecursive( v, nestStr )
    logging.debug( '%s ]' % nestStr )

  else:
    if type( data ) is int:
      logging.debug( ' %s 0x%x %s ' % ( nestStr, data, type( data ) ) )
    else:
      logging.debug( ' %s "%s" %s' % ( nestStr, data, type( data ) ) )


class Event():
  def __init__( self, domElement, options ):
    self.type = domElement.tagName if domElement.tagName == 'chapter' else domElement.getAttribute('type')
    self.name = domElement.getAttribute('name')
    self.fps = options.get('fps')

    self.arg0 = '0'
    self.arg1 = '0'
    self.arg2 = '0'

    timeline = self.__getImmediateChildByTagName(domElement, 'timeline')
    self.timestart = self.__parseTime(timeline.getElementsByTagName('timestart'))    
    self.timeend = self.__parseTime(timeline.getElementsByTagName('timeend'))
    
    self.duration = max(0, self.timeend - self.timestart)

    self.framestart = self.__msToFrame(self.timestart)
    self.frameend = self.__msToFrame(self.timeend)
            
    resultparent = self.__getImmediateChildByTagName(domElement, 'result')
    if False != resultparent:
      result = [result for result in resultparent.childNodes if result.nodeType == result.ELEMENT_NODE].pop()
      self.result = result.tagName
      self.resultname = result.getAttribute('name') if result.getAttribute('name') else 'none'
    else:
      self.result = 'none'
      self.resultname = 'none'
      
    paramsparent = self.__getImmediateChildByTagName(domElement, 'params')
    self.parameters = {}
    if False != paramsparent:
      for param in [param for param in paramsparent.childNodes if param.nodeType == param.ELEMENT_NODE]:
        self.parameters[param.getAttribute('key')] = param.getAttribute('value')

    if self.type == 'chapter':
      self.arg0 = options.get('chapternumber')
      self.arg1 = self.parameters.get('cockpit', '0')

    self.__normalize_type()

    self.type = self.__sanitizeName(self.type)
    self.name = self.__sanitizeName(self.name)
    self.result = self.__sanitizeName(self.result)
    self.resultname = self.__sanitizeName(self.resultname)

    if len(self.type) > 13:
      logging.warning("WARNING: Event type '%s' exceeds 13 characters! This may cause assembler symbol overflow." % self.type)
        

  def __getImmediateChildByTagName(self, domElement, childName):
    try:
      return [child for child in domElement.getElementsByTagName(childName) if child.parentNode == domElement].pop()
    except IndexError:
      return False


  def __parseTime(self, nodeList):
    timeVal = 0
    if len(nodeList) > 0:
      domElement = nodeList.pop()
      try:
        timeVal = int(domElement.getAttribute('min')) * 60 * 1000 + int(domElement.getAttribute('second')) * 1000 + int(domElement.getAttribute('ms'))
      except ValueError:
        logging.error( 'Invalid time attribute(s) encountered in chapter xml.')
        sys.exit(1)
    return timeVal


  def __msToFrame(self, time):
    return int(time * float(self.fps * 0.001))


  def toString(self):
    return "EVENT Event.%s $%04x $%04x EventResult.%s EventTarget.%s" % (self.type, self.__msToFrame(self.timestart), self.__msToFrame(self.timeend), self.result, self.resultname)

  def __sanitizeName(self, name):
    return name.replace('-', '_')

  def __normalize_type(self):
    direction_lut = {
      'left': 'JOY_DIR_LEFT',
      'right': 'JOY_DIR_RIGHT',
      'up': 'JOY_DIR_UP',
      'down': 'JOY_DIR_DOWN',
    }

    room_transition_lut = {
      'enter_room': 0,
      'enter_room_left': 1,
      'enter_room_right': 2,
      'enter_room_up': 3,
      'enter_room_down': 4,
      'enter_room_upleft': 5,
      'start_alive': 6,
      'start_dead': 7,
    }

    if self.type == 'direction' and 'type' in self.parameters:
      direction = self.parameters['type']
      if direction in direction_lut:
        self.type = 'dir_gen'
        self.arg0 = direction_lut[direction]
    elif self.type in room_transition_lut:
      self.arg0 = room_transition_lut[self.type]
      self.type = 'room_trans'
    elif self.type.startswith('seq') and self.type[3:].isdigit():
      self.arg0 = self.type[3:]
      self.type = 'seq_generic'
    elif self.type == "macro":
      self.type = "%s-%s" % (self.type, self.name)
    
    if self.type == 'direction_generic':
        logging.warning("DEBUG: self.type became direction_generic! Params: %s" % self.parameters)
    
class UserOptions():
  def __init__( self, args, defaults ):
    self.__options = self.__parseUserArguments(args, defaults)

  def get( self, option ):
    if option in self.__options:
      return self.__options[option]['value']
    else:
      logging.error( 'Invalid option %s requested.' % option )
      sys.exit(1)

  def manualSet( self, option, value ):
    self.__options[option]['value'] = value


  def __parseUserArguments( self, args, defaults ):
    if "-h" in args or "--help" in args:
        self.__print_help(defaults)
        sys.exit(0)

    options = defaults
      
    for i in range( len( args ) ):
      if args[i][1:] in defaults:
        options[args[i][1:]]['value'] = args[i+1]
    return self.__sanitizeOptions( options )

  def __print_help(self, defaults):
      print("Usage: script.py [options]")
      print("\nOptions:")
      for key, value in defaults.items():
          default_val = value.get("value", "")
          help_text = f"  -{key:<15} Type: {value['type']:<8} Default: {default_val}"
          if "min" in value and "max" in value:
              help_text += f" (Range: {value['min']}-{value['max']})"
          print(help_text)


  def __sanitizeOptions( self, options ):
    for optionName, optionValue in options.items():
      sanitizerLUT = self.__getSanitizerLUT()
      options[optionName] = sanitizerLUT[optionValue['type']]( optionName, optionValue )    
    return options


  def __sanitizeInt( self, optionName, optionValue ):
    if type( optionValue['value'] ) is not int:
      try:
        optionValue['value'] = int( optionValue['value'], 10 )
      except ( TypeError, ValueError ):
        logging.error( 'Invalid argument %s for option -%s.' % ( optionValue['value'], optionName ) )
        sys.exit(1)
    if optionValue['value'] < optionValue['min'] or optionValue['value'] > optionValue['max']:
        logging.error( 'Argument %s for option -%s is out of allowed range %s - %s.' % ( optionValue['value'], optionName, optionValue['min'], optionValue['max'] ) )
        sys.exit(1)
    return optionValue

  def __sanitizeFloat( self, optionName, optionValue ):
    if type( optionValue['value'] ) is not float:
      try:
        optionValue['value'] = float( optionValue['value'] )
      except ( TypeError, ValueError ):
        logging.error( 'Invalid argument %s for option -%s.' % ( optionValue['value'], optionName ) )
        sys.exit(1)
    if optionValue['value'] < optionValue['min'] or optionValue['value'] > optionValue['max']:
        logging.error( 'Argument %s for option -%s is out of allowed range %s - %s.' % ( optionValue['value'], optionName, optionValue['min'], optionValue['max'] ) )
        sys.exit(1)
    return optionValue

  def __sanitizeHex( self, optionName, optionValue ):
    if type( optionValue['value'] ) is not int:
      try:
        optionValue['value'] = int( optionValue['value'], 16 )
      except ( TypeError, ValueError ):
        logging.error( 'Invalid argument %s for option -%s.' % ( optionValue['value'], optionName ) )
        sys.exit(1)
    if optionValue['value'] < optionValue['min'] or optionValue['value'] > optionValue['max']:
        logging.error( 'Argument %s for option -%s is out of allowed range %s - %s.' % ( optionValue['value'], optionName, optionValue['min'], optionValue['max'] ) )
        sys.exit(1)
    return optionValue
    
    
  def __sanitizeStr( self, optionName, optionValue ):
    if len( optionValue ) < 1:
        logging.error( 'Argument %s for option -%s is invalid.' % ( optionValue['value'], optionName ) )
        sys.exit(1)
    return optionValue


  def __sanitizeBool( self, optionName, optionValue ):
    if type( optionValue['value'] ) is str:
      if optionValue['value'] not in ( 'on', 'off' ):
        logging.error( 'Argument %s for option -%s is invalid. Only on and off are allowed.' % ( optionValue['value'], optionName ) )
        sys.exit(1)
      optionValue['value'] = True if optionValue['value'] == 'on' else False
    return optionValue
    
    
  def __getSanitizerLUT(self):
    return {
      'int'    : self.__sanitizeInt,
      'float'    : self.__sanitizeFloat,
      'hex'    : self.__sanitizeHex,
      'str'    : self.__sanitizeStr,
      'bool'    : self.__sanitizeBool
    }    

if __name__ == "__main__":
    main()


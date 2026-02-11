#!/usr/bin/env python3

__author__ = "Matthias Nagler <matt@dforce.de>"
__url__ = ("dforce3000", "dforce3000.de")
__version__ = "0.1"

"""
Package multiple animation chapters and their audio into a single MSU-1 data file.
"""

import logging
import os
import sys

from userOptions import Options

logging.basicConfig(level=logging.INFO, format='%(message)s')

HEADER_SIZE = 0x20
CHAPTER_SIZE = 0x4
POINTER_SIZE = 0x4
FRAME_SIZE = 0x6
MAX_CHAPTERS = 0x7ff

TILES = 0
TILEMAP = 1
PALETTE = 2


def main():
    options = Options(
        sys.argv,
        {
            'bpp': {'value': 4, 'type': 'int', 'max': 8, 'min': 1},
            'infilebase': {'value': '', 'type': 'str'},
            'outfile': {'value': '', 'type': 'str'},
            'title': {'value': '', 'type': 'str'},
            'fps': {'value': 24, 'type': 'int', 'max': 60, 'min': 1},
        },
    )

    if not os.path.exists(options.get('infilebase')):
        logging.error('Chapter base-folder "%s" is nonexistant.' % options.get('infilebase'))
        sys.exit(1)

    chapters = sorted(
        [ch for ch in [Chapter(chapterDir, options) for root, dirs, _ in os.walk(options.get('infilebase')) for chapterDir in dirs] if ch.frames],
        key=lambda chapter: chapter.id,
    )

    if not chapters:
        logging.error('No chapter folders are present inside specified chapter base folder %s.' % options.get('infilebase'))
        sys.exit(1)

    maxChapterId = max(ch.id for ch in chapters)
    if maxChapterId + 1 > MAX_CHAPTERS:
        logging.error('Too many chapters, maximum of %s are allowed, %s are present (max id %s).' % (MAX_CHAPTERS, len(chapters), maxChapterId))
        sys.exit(1)

    outFile = getOutFile(options.get('outfile'))
    outFile.write(b"S-MSU1")
    outFile.write(("%-21.21s" % options.get('title').upper()).encode('ascii'))
    if options.get('bpp') == 2:
        colorDepth = 4
    elif options.get('bpp') == 4:
        colorDepth = 5
    elif options.get('bpp') == 8:
        colorDepth = 6
    else:
        logging.error('Invalid color depth %s.' % options.get('bpp'))
        sys.exit(1)

    outFile.write(bytes((colorDepth,)))
    outFile.write(bytes((options.get('fps'),)))

    # chapter count as 2 bytes (little-endian), for >255 chapter support
    totalChapters = max(ch.id for ch in chapters) + 1 if chapters else 0
    outFile.write(bytes((totalChapters & 0xff,)))
    outFile.write(bytes(((totalChapters >> 8) & 0xff,)))

    for _ in range(HEADER_SIZE - outFile.tell()):
        outFile.write(b"\x00")

    # Build dense chapter map (indexed by chapter ID, entries for all IDs 0..max)
    chapterById = {ch.id: ch for ch in chapters}

    # Dense pointer table: one entry for every ID from 0 to max
    scenePointerOffset = HEADER_SIZE
    sceneOffset = scenePointerOffset + (totalChapters * POINTER_SIZE)

    # Add a dummy chapter entry for empty/missing IDs (0 frames)
    # Dummy chapter: ID(1) + frameCount(3) = 4 bytes, no frame pointers
    dummyChapterOffset = sceneOffset
    dummyChapterSize = CHAPTER_SIZE  # just the header, 0 frames

    # Compute scene data offsets (after dummy chapter)
    realSceneOffset = dummyChapterOffset + dummyChapterSize
    frameOffset = realSceneOffset
    for chapter in chapters:
        frameOffset += CHAPTER_SIZE + (len(chapter.frames) * POINTER_SIZE)

    # Write dense pointer table
    outFile.seek(scenePointerOffset)
    pointer = realSceneOffset
    for chId in range(totalChapters):
        if chId in chapterById:
            writePointer(outFile, pointer)
            ch = chapterById[chId]
            pointer += CHAPTER_SIZE + (len(ch.frames) * POINTER_SIZE)
        else:
            # Point to dummy chapter entry
            writePointer(outFile, dummyChapterOffset)

    # Write dummy chapter entry (0 frames)
    outFile.seek(dummyChapterOffset)
    outFile.write(bytes((0xff,)))  # dummy ID
    outFile.write(bytes((0,)))     # frameCount low = 0
    outFile.write(bytes((0,)))     # frameCount mid = 0
    outFile.write(bytes((0,)))     # frameCount high = 0

    # Write real chapter data
    outFile.seek(realSceneOffset)
    pointer = frameOffset
    for chapter in chapters:
        logging.debug('Now writing scene %02d (%s) at offset 0x%08x.' % (chapter.id, chapter.name, outFile.tell()))
        outFile.write(bytes((chapter.id & 0xff,)))
        outFile.write(bytes((len(chapter.frames) & 0xff,)))
        outFile.write(bytes(((len(chapter.frames) & 0xff00) >> 8,)))
        outFile.write(bytes(((len(chapter.frames) & 0xff0000) >> 16,)))
        for frame in chapter.frames:
            writePointer(outFile, pointer)
            pointer += FRAME_SIZE + frame.length

        chapterAudioFileName = "%s-%d.pcm" % (os.path.splitext(options.get('outfile'))[0], chapter.id)
        logging.debug('Now writing audio file %s of scene %02d (%s).' % (chapterAudioFileName, chapter.id, chapter.name))
        audioOutFile = getOutFile(chapterAudioFileName)
        for byte in chapter.audio:
            audioOutFile.write(byte if isinstance(byte, (bytes, bytearray)) else bytes((byte,)))

    outFile.seek(frameOffset)
    for chapter in chapters:
        frameId = 0
        for frame in chapter.frames:
            logging.debug(
                'Now writing frame %s of scene %02d (%s) at offset 0x%08x.'
                % (frame.name, chapter.id, chapter.name, outFile.tell())
            )
            lengthHeader = ((len(frame.tilemap) // 2) & 0x7ff) | (((len(frame.tiles) >> colorDepth) & 0x7ff) << 11) | (
                ((len(frame.palette) // 2) & 0xff) << 22
            )
            outFile.write(bytes((frameId & 0xff,)))
            outFile.write(bytes(((frameId & 0xff00) >> 8,)))
            outFile.write(bytes((lengthHeader & 0xff,)))
            outFile.write(bytes(((lengthHeader & 0xff00) >> 8,)))
            outFile.write(bytes(((lengthHeader & 0xff0000) >> 16,)))
            outFile.write(bytes(((lengthHeader & 0xff000000) >> 24,)))
            outFile.write(frame.tilemap)
            outFile.write(frame.tiles)
            outFile.write(frame.palette)
            frameId += 1

    outFile.close()
    logging.info(
        'Successfully wrote msu1 data file %s, processed %s chapters containing %s frames.'
        % (options.get('outfile'), len(chapters), len([frame for chapter in chapters for frame in chapter.frames]))
    )


def writePointer(fileHandle, pointer):
    fileHandle.write(bytes((pointer & 0xff,)))
    fileHandle.write(bytes(((pointer & 0xff00) >> 8,)))
    fileHandle.write(bytes(((pointer & 0xff0000) >> 16,)))
    fileHandle.write(bytes(((pointer & 0xff000000) >> 24,)))


class Chapter:
    def __init__(self, chapterDir, options):
        self.name = chapterDir
        self.path = '%s/%s/' % (options.get('infilebase'), chapterDir)

        if not os.path.exists(self.path):
            logging.error('Chapter folder "%s" is nonexistant.' % self.path)
            sys.exit(1)

        idFiles = [idFile for root, dirs, files in os.walk(self.path) for idFile in sorted(files) if idFile.find("chapter.id") >= 0]
        if len(idFiles) != 1:
            logging.error('Chapter folder %s must contain exactly one id file, but actually contains %s.' % (chapterDir, len(idFiles)))
            sys.exit(1)

        idFile = idFiles.pop()
        id_suffix = idFile.split('chapter.id')[-1].lstrip('.')
        try:
            self.id = int(id_suffix)
        except ValueError:
            logging.error('Invalid chapter id in id-file %s.' % idFile)
            sys.exit(1)

        self.frames = [Frame(os.path.splitext(frameBaseFile)[0], self.path, options) for root, dirs, files in os.walk(self.path) for frameBaseFile in sorted(files) if frameBaseFile.find("gfx_video.tiles") >= 0]

        if self.frames:
            self.frames.append(self.frames[-1])
            self.frames.append(self.frames[-1])

        audioFiles = [audio for root, dirs, files in os.walk(self.path) for audio in sorted(files) if audio.find("sfx_video.pcm") >= 0]
        if len(audioFiles) != 1:
            logging.warning('Chapter folder %s does not contain exactly one msu1 pcm audio file. Proceeding without audio.' % chapterDir)
            self.audio = b''
        else:
            with getInFile('%s%s' % (self.path, audioFiles.pop())) as audioFile:
                self.audio = audioFile.read()


class Frame:
    def __init__(self, frameFileBase, path, options):
        self.name = frameFileBase
        with getInFile('%s%s.tiles' % (path, frameFileBase)) as tempFile:
            self.tiles = tempFile.read()
        with getInFile('%s%s.tilemap' % (path, frameFileBase)) as tempFile:
            self.tilemap = tempFile.read()
        with getInFile('%s%s.palette' % (path, frameFileBase)) as tempFile:
            self.palette = tempFile.read()
        self.length = len(self.tiles) + len(self.tilemap) + len(self.palette)


def getOutFile(fileName):
    try:
        outFile = open(fileName, 'wb')
    except IOError:
        logging.error('unable to access required output-file %s' % fileName)
        sys.exit(1)
    return outFile


def getInFile(fileName):
    try:
        inFile = open(fileName, 'rb')
    except IOError:
        logging.error('unable to access required input-file %s' % fileName)
        sys.exit(1)
    return inFile


if __name__ == "__main__":
    main()

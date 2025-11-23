
CC=gcc
LD=gcc

CFLAGS?= -c -O3 -ansi -pedantic -Wall
LDFLAGS =
WLAFLAGS = $(CFLAGS) -DUNIX

CFILES = main.c memory.c parse.c files.c check.c analyze.c write.c compute.c discard.c listfile.c
HFILES = main.h memory.h parse.h files.h check.h analyze.h write.h compute.h discard.h listfile.h defines.h
OFILES = main.o memory.o parse.o files.o check.o analyze.o write.o compute.o discard.o listfile.o


all: $(OFILES) 
	$(LD) $(OFILES) $(LDFLAGS) -o wlalink ; strip wlalink

main.o: main.c defines.h main.h 
	$(CC) $(WLAFLAGS) main.c

memory.o: memory.c defines.h memory.h 
	$(CC) $(WLAFLAGS) memory.c

parse.o: parse.c defines.h parse.h 
	$(CC) $(WLAFLAGS) parse.c

files.o: files.c defines.h files.h 
	$(CC) $(WLAFLAGS) files.c

check.o: check.c defines.h check.h 
	$(CC) $(WLAFLAGS) check.c

analyze.o: analyze.c defines.h analyze.h 
	$(CC) $(WLAFLAGS) analyze.c

write.o: write.c defines.h write.h 
	$(CC) $(WLAFLAGS) write.c

compute.o: compute.c defines.h compute.h 
	$(CC) $(WLAFLAGS) compute.c

discard.o: discard.c defines.h discard.h 
	$(CC) $(WLAFLAGS) discard.c

listfile.o: listfile.c defines.h listfile.h 
	$(CC) $(WLAFLAGS) listfile.c


$(OFILES): $(HFILES)


clean:
	rm -f $(OFILES) core *~ wlalink

install:
	cp wlalink /usr/local/bin

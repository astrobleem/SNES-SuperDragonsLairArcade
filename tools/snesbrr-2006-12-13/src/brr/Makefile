include ../makeinclude


LIBS = -lbase
CPPFLAGS += -I"../"
LDFLAGS += -L"../"
CFLAGS += -O3

BIN := ../snesbrr.exe
SRC := $(wildcard *.cpp)
OBJ := $(addsuffix .o,$(SRC))
DEP := $(addsuffix .d,$(SRC))


.PHONY : all clean distclean compress

all : $(BIN)

clean :
	-$(RM) $(OBJ)
	-$(RM) $(BIN)

distclean : clean
	-$(RM) $(DEP)

compress :
	-upx --best $(BIN)

$(BIN) : $(OBJ) ../libbase.a
	@echo "Linking $(words $(OBJ)) Object Files Into $@"; $(CXX) $(OBJ) -o $@ $(LDFLAGS) $(LIBS)


ifeq ($(findstring $(MAKECMDGOALS),clean distclean compress),)
 -include $(DEP)
endif


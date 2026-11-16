# GS/OS Make file for Freegemas IIGS
PROGRAM := FREEGEMAS
TARGETOBJDIR := obj
SRCDIR := src

CADIUS := cadius.exe
TEMPLATE_DISK := appleIIgs/gsos-template.2mg
DISK := freegemas.2mg
VOLUME := FREEGEMAS

SOURCES := $(wildcard $(SRCDIR)/*.c)
OBJECTS := $(subst .c,.ROOT,$(subst $(SRCDIR),$(TARGETOBJDIR),$(SOURCES)))
LINK_OBJS := $(subst .ROOT,,$(OBJECTS))

define LINK_OBJS_NAMES
	$(LINK_OBJS)
endef
export LINK_OBJS_NAMES

.PHONY: all clean dsk

all: $(PROGRAM)

$(TARGETOBJDIR)/%.ROOT: $(SRCDIR)/%.c
	iix compile +w $< keep=$(subst /,:,$(basename $@))

$(PROGRAM): $(OBJECTS)
	@echo $(LINK_OBJS_NAMES) > link.scp
	iix chtyp -l LINKER link.scp
	iix link +S link.scp keep=$@

dsk: all
	-del /F /Q $(DISK)
	copy $(TEMPLATE_DISK) $(DISK)
	$(CADIUS) ADDFILE $(DISK) /$(VOLUME) ./$(PROGRAM)

clean:
	-del /F /Q $(TARGETOBJDIR)\*.ROOT
	-del /F /Q $(PROGRAM)
	-del /F /Q link.scp
